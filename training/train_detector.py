"""
Supervised Adversarial Detector -- the blue-team answer to the white-box attack.
================================================================================
The one-class IF/OCSVM models only learned "far from normal", so an adversary who
hugs the normal boundary evades them (100% white-box evasion, see run_attacks.py).

This detector is different in two ways:
  1. SUPERVISED. It's a RandomForest trained on labeled normal-vs-attack data, so
     it learns the actual attack boundary, not just a distance-from-normal radius.
  2. ADVERSARIALLY HARDENED. A one-shot classifier could be re-evaded by re-
     optimizing the white-box attack against it. So we run an adversarial-training
     loop: attack the current model, feed the fresh evasions back as labeled
     attacks, retrain -- repeat until the attacker can no longer evade while
     staying malicious.

Convergence metric (the honest one):
  We measure "malicious evasions" -- points the model calls NORMAL that are still
  meaningfully anomalous (beyond the 95th-percentile radius of the real normal
  cloud, in scaled z-space). As training hardens the boundary, the attacker is
  forced ever closer to genuinely-normal readings; malicious evasions collapse
  toward zero. At that point the only way to "evade" is to stop attacking.

Outputs:
  models/detector.pkl            - the hardened classifier (raw sensor features)
  data/detector_training.csv     - per-round convergence log (for plotting)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'attacker'))
from config import *

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier

from adversarial_whitebox import load_ensemble, NORMAL_CENTROID
from run_attacks import (
    gen_baseline_aggressive, gen_adaptive_fuzzing, gen_whitebox_adversarial,
)

RNG = np.random.default_rng(7)


# ── Data helpers ────────────────────────────────────────────────────────────
def load_normal():
    """The genuine normal traffic the whole system is calibrated on."""
    df = pd.read_csv(FINAL_DATASET)
    return df[df["detected"] == 0][MODEL_FEATURES].to_numpy(dtype=float)


def z_distance(vectors, scaler):
    """How anomalous each row is, in standard-deviations from normal (L2 of the
    scaled vector). Small = looks normal, large = obviously off."""
    scaled = scaler.transform(pd.DataFrame(vectors, columns=MODEL_FEATURES))
    return np.linalg.norm(scaled, axis=1)


def random_attack_seeds(k):
    """Blatantly malicious seeds spread across many directions so the boundary is learned everywhere."""
    return np.column_stack([
        RNG.uniform(10, 45, k),      # temperature
        RNG.uniform(990, 1030, k),   # pressure
        RNG.uniform(40, 90, k),      # humidity
    ]).astype(float)


def craft_against(clf, seed, steps=80):
    """
    White-box boundary attack against the SUPERVISED detector `clf`.
    Walk the malicious seed toward the normal centroid; return the first point
    the classifier labels NORMAL (predict == 0) -- the closest-to-malicious
    evasion. Returns None if the classifier flags the whole path.
    """
    seed = np.asarray(seed, dtype=float)
    direction = NORMAL_CENTROID - seed
    for i in range(1, steps + 1):
        cand = seed + (i / steps) * direction
        if clf.predict(pd.DataFrame([cand], columns=MODEL_FEATURES))[0] == 0:
            return cand
    return None


def mine_evasions(clf, k, radius, scaler):
    """
    Attack the current detector from `k` diverse malicious seeds.
    Returns (malicious_evasions, n_malicious_evasions):
      malicious_evasions -- evasion points that are STILL anomalous (z >= radius);
                            these are the hard negatives we retrain on.
    Evasion points that fell inside the normal cloud are ignored: at that point
    the "attack" has become genuinely normal traffic and flagging it would just
    create false positives.
    """
    seeds = random_attack_seeds(k)
    evasions = []
    for s in seeds:
        pt = craft_against(clf, s)
        if pt is not None:
            evasions.append(pt)
    if not evasions:
        return np.empty((0, len(MODEL_FEATURES))), 0
    evasions = np.array(evasions)
    zdist = z_distance(evasions, scaler)
    malicious = evasions[zdist >= radius]      # evaded AND still an attack
    return malicious, len(malicious)


# ── Training ────────────────────────────────────────────────────────────────
def build_initial_attacks(n, ens_model, scaler, ocsvm):
    """Seed the attack class with a diverse mix so round 0 already generalizes:
    blatant attacks + heuristic fuzzing + white-box adversarial examples."""
    atk = []
    atk += gen_baseline_aggressive(n)
    atk += gen_adaptive_fuzzing(n)
    atk += gen_whitebox_adversarial(n, ens_model, scaler, ocsvm)
    return np.array(atk, dtype=float)


def train():
    print("=" * 70)
    print("  BLUE TEAM -- Supervised Adversarial Detector (RandomForest)")
    print("=" * 70)

    ens_model, scaler, ocsvm = load_ensemble()   # reuse the fitted scaler
    X_norm = load_normal()

    # Radius of the real normal cloud in z-space; the target the attacker is
    # driven back to. Beyond it = "still an attack".
    norm_z = z_distance(X_norm, scaler)
    radius = float(np.percentile(norm_z, 95))
    print(f"  Normal samples: {len(X_norm)}   normal-cloud radius (z, p95): {radius:.2f}\n")

    # Round 0 training set: normal + a diverse initial attack corpus.
    X_atk = build_initial_attacks(400, ens_model, scaler, ocsvm)
    X = np.vstack([X_norm, X_atk])
    y = np.concatenate([np.zeros(len(X_norm)), np.ones(len(X_atk))])

    history = []
    clf = None
    for rnd in range(ADV_TRAIN_ROUNDS + 1):
        clf = RandomForestClassifier(**DETECTOR_PARAMS)
        clf.fit(pd.DataFrame(X, columns=MODEL_FEATURES), y)

        # Attack the freshly-trained model and count malicious evasions remaining.
        malicious, n_evade = mine_evasions(clf, ADV_SAMPLES_PER_ROUND, radius, scaler)
        evasion_rate = n_evade / ADV_SAMPLES_PER_ROUND * 100
        n_attacks = int(y.sum())
        print(f"  Round {rnd}: train_attacks={n_attacks:5d}  "
              f"malicious_evasions={n_evade:4d}/{ADV_SAMPLES_PER_ROUND}  "
              f"({evasion_rate:5.1f}%)")
        history.append({
            "round": rnd,
            "train_attacks": n_attacks,
            "malicious_evasions": n_evade,
            "evasion_rate_%": round(evasion_rate, 1),
        })

        if rnd == ADV_TRAIN_ROUNDS:
            break

        # Harden: add the malicious evasions as attack examples and retrain.
        if len(malicious) > 0:
            X = np.vstack([X, malicious])
            y = np.concatenate([y, np.ones(len(malicious))])
        else:
            print("  No malicious evasions left -- attacker forced to go normal. "
                  "Converged early.")
            break

    # ── Save ────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(DETECTOR_MODEL_PATH), exist_ok=True)
    joblib.dump(clf, DETECTOR_MODEL_PATH)
    hist_path = os.path.join(BASE_DIR, "data", "detector_training.csv")
    pd.DataFrame(history).to_csv(hist_path, index=False)

    first, last = history[0]["evasion_rate_%"], history[-1]["evasion_rate_%"]
    print(f"\n  [+] Detector saved       -> {DETECTOR_MODEL_PATH}")
    print(f"  [+] Convergence log      -> {hist_path}")
    print(f"  [+] Malicious evasion rate: {first:.1f}%  ->  {last:.1f}%  "
          f"across {len(history)-1} hardening rounds")
    print("\n  Next: python training/eval_detector.py  (before/after vs the old IDS)\n")


if __name__ == "__main__":
    train()
