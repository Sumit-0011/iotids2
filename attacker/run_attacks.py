"""
Reproducible evasion benchmark -- PROOF OF BYPASS.
==================================================
Runs each attack strategy OFFLINE against the exact ensemble the server uses
(Isolation Forest + One-Class SVM) and quantifies how well each one bypasses
detection. No running server required -- this is the deterministic evidence you
can put in a report or slide.

Strategies compared:
  1. baseline_aggressive  -- blatant attack packets (control: should be caught)
  2. adaptive_fuzzing     -- heuristic feedback fuzzer's payload distribution
  3. whitebox_adversarial -- minimal-perturbation boundary search (full white-box)

Outputs:
  - a printed comparison table (evasion rate, detector-by-detector breakdown)
  - data/attack_report.csv     : the table, for plotting / reporting
  - data/evasive_samples.csv   : every undetected attack packet (seed corpus for
                                 the future blue-team detector)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import numpy as np
import pandas as pd

from adversarial_whitebox import (
    load_ensemble, ensemble_flags, craft_adversarial,
    ATTACK_SEED, NORMAL_CENTROID,
)

RNG = np.random.default_rng(42)   # fixed seed -> reproducible report


# ── Attack sample generators (each returns a list of raw feature vectors) ────
def gen_baseline_aggressive(n):
    """Phase-3 style blatant attack: extreme shifts. The control case."""
    out = []
    for _ in range(n):
        out.append([
            25.0 + RNG.uniform(10, 20),    # 35-45 C
            60.0 + RNG.uniform(15, 25),    # 75-85 %
            RNG.integers(0, 2),
            40.0 + RNG.uniform(40, 80),    # 80-120 dB
            80.0 - RNG.uniform(5, 15),
        ])
    return out


def gen_adaptive_fuzzing(n):
    """The heuristic fuzzer jitters around baselines with growing fuzz. We sweep
    fuzz 1..8 the way the feedback loop would, jittering each sensor."""
    out = []
    base = np.array([25.0, 60.0, 0.0, 40.0, 80.0])
    for i in range(n):
        fuzz = 1 + (i % 8)
        v = base.copy()
        v[0] += RNG.uniform(-fuzz, fuzz)
        v[1] += RNG.uniform(-fuzz, fuzz)
        v[3] += RNG.uniform(-fuzz, fuzz)
        v[2] = RNG.integers(0, 2)
        out.append(v.tolist())
    return out


def gen_whitebox_adversarial(n, model, scaler, ocsvm):
    """Minimal-perturbation adversarial examples from the white-box search."""
    out = []
    for _ in range(n):
        jitter = RNG.uniform(-2, 2, size=5)
        jitter[2] = 0
        seed = ATTACK_SEED + jitter
        adv, _pert, _score = craft_adversarial(seed, model, scaler, ocsvm)
        if adv is not None:
            out.append(list(adv))
    return out


def anomaly_distance(vec):
    """How far the sample sits from the normal centroid (L2). Bigger = more
    obviously malicious. Used to show white-box samples still deviate."""
    return float(np.linalg.norm(np.array(vec) - NORMAL_CENTROID))


def evaluate(name, samples, model, scaler, ocsvm):
    """Score a batch of attack vectors; return a stats row + evasive samples."""
    n = len(samples)
    if n == 0:
        return None, []
    if_caught = svm_caught = ens_caught = 0
    evasive = []
    for v in samples:
        flagged, if_flag, svm_flag, _ = ensemble_flags(v, model, scaler, ocsvm)
        if_caught += if_flag
        svm_caught += svm_flag
        ens_caught += flagged
        if flagged == 0:
            row = dict(zip(MODEL_FEATURES, [round(float(x), 3) for x in v]))
            row["attack"] = name
            row["anomaly_dist"] = round(anomaly_distance(v), 2)
            evasive.append(row)
    evaded = n - ens_caught
    row = {
        "attack": name,
        "packets": n,
        "detected": ens_caught,
        "evaded": evaded,
        "evasion_rate_%": round(evaded / n * 100, 1),
        "if_detect_%": round(if_caught / n * 100, 1),
        "svm_detect_%": round(svm_caught / n * 100, 1),
        "mean_anomaly_dist": round(float(np.mean([anomaly_distance(v) for v in samples])), 2),
    }
    return row, evasive


def main(n=200):
    print("=" * 70)
    print("  IoT IDS -- ADVERSARIAL EVASION BENCHMARK (proof of bypass)")
    print("=" * 70)
    model, scaler, ocsvm = load_ensemble()
    print(f"  Defender: Isolation Forest + "
          f"{'One-Class SVM (ensemble)' if ocsvm is not None else 'IF only'}, "
          f"rule='{ENSEMBLE_RULE}'")
    print(f"  Packets per strategy: {n}\n")

    strategies = {
        "baseline_aggressive": gen_baseline_aggressive(n),
        "adaptive_fuzzing": gen_adaptive_fuzzing(n),
        "whitebox_adversarial": gen_whitebox_adversarial(n, model, scaler, ocsvm),
    }

    rows, all_evasive = [], []
    for name, samples in strategies.items():
        row, evasive = evaluate(name, samples, model, scaler, ocsvm)
        if row:
            rows.append(row)
            all_evasive.extend(evasive)

    report = pd.DataFrame(rows)

    # ── Print the comparison table ──────────────────────────────────────────
    print("  RESULTS")
    print("  " + "-" * 66)
    header = f"  {'strategy':<22}{'pkts':>5}{'evaded':>8}{'evasion%':>10}{'IF%':>7}{'SVM%':>7}"
    print(header)
    print("  " + "-" * 66)
    for _, r in report.iterrows():
        print(f"  {r['attack']:<22}{r['packets']:>5}{r['evaded']:>8}"
              f"{r['evasion_rate_%']:>9}%{r['if_detect_%']:>7}{r['svm_detect_%']:>7}")
    print("  " + "-" * 66)

    # ── Save artifacts ──────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(FINAL_DATASET), exist_ok=True)
    report_path = os.path.join(BASE_DIR, "data", "attack_report.csv")
    evasive_path = os.path.join(BASE_DIR, "data", "evasive_samples.csv")
    report.to_csv(report_path, index=False)
    pd.DataFrame(all_evasive).to_csv(evasive_path, index=False)

    print(f"\n  [+] Report saved      -> {report_path}")
    print(f"  [+] Evasive corpus    -> {evasive_path}  ({len(all_evasive)} samples)")
    print("\n  INTERPRETATION")
    best = report.sort_values('evasion_rate_%', ascending=False).iloc[0]
    print(f"  '{best['attack']}' bypassed the current IDS on "
          f"{best['evasion_rate_%']}% of packets.")
    print("  The evasive corpus is the seed data for the next-gen detector.\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Adversarial evasion benchmark")
    ap.add_argument("-n", type=int, default=200, help="packets per strategy")
    args = ap.parse_args()
    main(n=args.n)
