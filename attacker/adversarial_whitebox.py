"""
White-box adversarial attack against the IoT IDS ensemble.
==========================================================
This attacker has FULL knowledge of the defender: it loads the exact same
`ids_model.pkl` (Isolation Forest), `scaler.pkl`, and `ocsvm_model.pkl`
(One-Class SVM) that the server uses. That makes this a genuine white-box
adversarial attack.

Goal (the classic adversarial-example objective):
    Start from a clearly MALICIOUS sample (an obvious attack the IDS catches)
    and find the SMALLEST perturbation that flips BOTH detectors' verdict from
    "anomaly" to "safe" -- so the packet is still an attack, just invisible.

Because Isolation Forest / One-Class SVM are non-differentiable (trees + kernel
boundary), we don't use gradients. Instead we run a guided boundary search
(coordinate hill-climb toward the normal centroid): repeatedly nudge the sample
a little toward "normal" until the ensemble stops flagging it, then stop -- that
first-evading point is the minimal-perturbation adversarial example.

Each crafted packet is also POSTed to the LIVE IDS so evasion is measured for
real, not just offline. Undetected packets are the proof of bypass.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import time
import argparse
import numpy as np
import pandas as pd
import joblib
import requests
import warnings
warnings.filterwarnings("ignore")


# ── Load the defender's exact models (white-box knowledge) ──────────────────
def load_ensemble():
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    ocsvm = joblib.load(OCSVM_MODEL_PATH) if os.path.exists(OCSVM_MODEL_PATH) else None
    return model, scaler, ocsvm


def _frame(vec):
    """Wrap a feature vector as a DataFrame with correct names (silences the
    sklearn 'X does not have valid feature names' warning cleanly)."""
    return pd.DataFrame([vec], columns=MODEL_FEATURES)


def ensemble_flags(vec, model, scaler, ocsvm):
    """Return (flagged, if_flag, svm_flag, if_score) for a raw feature vector.
    `flagged` follows the server's ENSEMBLE_RULE ('or' by default)."""
    scaled = scaler.transform(_frame(vec))
    if_flag = 1 if model.predict(scaled)[0] == -1 else 0
    if_score = float(model.decision_function(scaled)[0])
    if ocsvm is not None:
        svm_flag = 1 if ocsvm.predict(scaled)[0] == -1 else 0
    else:
        svm_flag = if_flag
    if ENSEMBLE_RULE == "and":
        flagged = 1 if (if_flag and svm_flag) else 0
    else:
        flagged = 1 if (if_flag or svm_flag) else 0
    return flagged, if_flag, svm_flag, if_score


# Normal-region centroid the search walks toward. Matches the training baseline
# (temp 25, press 1013.25, hum 60).
NORMAL_CENTROID = np.array([25.0, 1013.25, 60.0])

# A blatantly malicious starting point the IDS should catch easily
ATTACK_SEED = np.array([40.0, 990.0, 80.0])


def craft_adversarial(seed, model, scaler, ocsvm, steps=60):
    """
    Minimal-perturbation boundary search.

    Walk the malicious `seed` toward the normal centroid in small steps. As soon
    as the ensemble stops flagging it, return that point -- it's the closest
    still-malicious sample that evades detection. If we reach the centroid and
    it's still flagged, evasion failed for this seed.

    Returns (evasive_vec_or_None, perturbation_L2, if_score_at_evasion).
    """
    seed = np.array(seed, dtype=float)
    direction = NORMAL_CENTROID - seed
    for i in range(1, steps + 1):
        alpha = i / steps                       # 0 -> 1 : seed -> centroid
        cand = seed + alpha * direction
        flagged, _, _, if_score = ensemble_flags(cand, model, scaler, ocsvm)
        if flagged == 0:
            pert = float(np.linalg.norm(cand - seed))
            return cand, pert, if_score
    return None, float(np.linalg.norm(NORMAL_CENTROID - seed)), None


def vec_to_payload(vec, tag="adv_whitebox", fuzz=0, interval=500):
    return {
        "device": tag,
        "temperature": round(float(vec[0]), 2),
        "pressure": round(float(vec[1]), 2),
        "humidity": round(float(vec[2]), 2),
        "fuzz": fuzz,
        "interval": interval,
    }


def run_whitebox(n=40, send=True, delay=1.0):
    print("[*] White-box adversarial attack -- loading defender models...")
    model, scaler, ocsvm = load_ensemble()
    print(f"[*] Ensemble loaded (OCSVM {'ACTIVE' if ocsvm is not None else 'absent'}, "
          f"rule='{ENSEMBLE_RULE}')")

    # Confirm the seed really is caught before we start evading it.
    seed_flag, sif, ssvm, _ = ensemble_flags(ATTACK_SEED, model, scaler, ocsvm)
    print(f"[*] Attack seed {ATTACK_SEED.tolist()} -> flagged={seed_flag} "
          f"(IF={sif}, SVM={ssvm})  [should be 1]\n")

    evaded = 0
    total = 0
    for i in range(1, n + 1):
        # Vary the seed slightly each round so we don't send identical packets.
        jitter = np.random.uniform(-2, 2, size=3)
        seed = ATTACK_SEED + jitter
        adv, pert, if_score = craft_adversarial(seed, model, scaler, ocsvm)

        if adv is None:
            print(f"[{i:02d}] no evasive point found (attack stayed detectable)")
            total += 1
            continue

        payload = vec_to_payload(adv)
        live_detected = None
        if send:
            try:
                r = requests.post(IDS_SERVER_URL, json=payload, timeout=2)
                live_detected = int(r.json().get("detected", -1))
            except requests.RequestException as e:
                print(f"[{i:02d}] IDS unreachable: {e}")
            except (ValueError, KeyError) as e:
                print(f"[{i:02d}] malformed IDS response: {e}")

        total += 1
        # Count as evasion when the LIVE server (or offline model if not sending)
        # returns 'not detected'.
        offline_flag, _, _, _ = ensemble_flags(adv, model, scaler, ocsvm)
        verdict = live_detected if live_detected is not None else offline_flag
        if verdict == 0:
            evaded += 1

        print(f"[{i:02d}] adv=[T{adv[0]:.1f} P{adv[1]:.1f} H{adv[2]:.1f}] "
              f"perturb(L2)={pert:5.2f}  IF_score={if_score:+.3f}  "
              f"live_detected={live_detected}  -> {'EVADED' if verdict == 0 else 'caught'}")
        if send:
            time.sleep(delay)

    rate = evaded / max(1, total) * 100
    print(f"\n[+] White-box evasion: {evaded}/{total} packets undetected ({rate:.1f}%)")
    if send:
        print("[+] These packets are logged in data/data2.csv with device=adv_whitebox")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="White-box adversarial attack on the IoT IDS")
    ap.add_argument("-n", type=int, default=40, help="number of adversarial packets")
    ap.add_argument("--offline", action="store_true",
                    help="don't POST to the server; evaluate against loaded models only")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between live packets")
    args = ap.parse_args()
    run_whitebox(n=args.n, send=not args.offline, delay=args.delay)
