"""
Evaluation script: before/after comparison of all three IDS detectors.
=======================================================================
Compares how well each generation of detector catches adversarial attacks
that were specifically crafted to evade the earlier models.

Detectors evaluated
  v1  -- Isolation Forest (original, one-class)
  v2  -- IF + One-Class SVM ensemble
  v3  -- IF + OCSVM + Supervised Adversarial RandomForest (triple ensemble)

Attack strategies
  baseline_aggressive  -- blatant, easily caught (control case)
  adaptive_fuzzing     -- heuristic feedback-loop fuzzer
  whitebox_adversarial -- minimal-perturbation white-box boundary search

Output
  Printed comparison table
  data/eval_report.csv  -- saved for plotting / reporting
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'attacker'))
from config import *

import numpy as np
import pandas as pd
import joblib

from adversarial_whitebox import (
    load_ensemble, ensemble_flags, craft_adversarial,
    ATTACK_SEED, NORMAL_CENTROID,
)
from run_attacks import (
    gen_baseline_aggressive, gen_adaptive_fuzzing, gen_whitebox_adversarial,
)

RNG = np.random.default_rng(42)


# ── Detector loaders ────────────────────────────────────────────────────────
def load_v1():
    """Isolation Forest only."""
    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler, None


def load_v2():
    """IF + One-Class SVM ensemble (original dual-detector)."""
    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    ocsvm  = joblib.load(OCSVM_MODEL_PATH) if os.path.exists(OCSVM_MODEL_PATH) else None
    return model, scaler, ocsvm


def load_v3_rf():
    """Supervised Adversarial RandomForest (trained on raw features)."""
    if not os.path.exists(DETECTOR_MODEL_PATH):
        return None
    return joblib.load(DETECTOR_MODEL_PATH)


# ── Scoring helpers ──────────────────────────────────────────────────────────
def score_ensemble(samples, model, scaler, ocsvm):
    """Score samples against the IF+OCSVM ensemble; return (detected_count, n)."""
    caught = 0
    for v in samples:
        flagged, _, _, _ = ensemble_flags(v, model, scaler, ocsvm)
        caught += flagged
    return caught, len(samples)


def score_triple(samples, model, scaler, ocsvm, detector_rf):
    """Score samples against the full triple-detector ensemble."""
    caught = 0
    for v in samples:
        flagged, if_f, svm_f, _ = ensemble_flags(v, model, scaler, ocsvm)
        rf_f = 0
        if detector_rf is not None:
            raw_df = pd.DataFrame([list(v)], columns=MODEL_FEATURES)
            rf_f = 1 if int(detector_rf.predict(raw_df)[0]) == 1 else 0
        # OR rule: flag if any detector fires
        if flagged or rf_f:
            caught += 1
    return caught, len(samples)


# ── Main ─────────────────────────────────────────────────────────────────────
def main(n=200):
    print("=" * 72)
    print("  IoT IDS — DETECTOR EVALUATION: v1 vs v2 vs v3")
    print("=" * 72)

    model, scaler, ocsvm = load_v2()   # shared models for v1/v2
    detector_rf = load_v3_rf()

    if detector_rf is None:
        print("\n  [!] detector.pkl not found — v3 column will show 'N/A'.")
        print(f"      Run: python training/train_detector.py\n")

    # Generate attack samples
    print(f"  Generating {n} samples per attack strategy...")
    strategies = {
        "baseline_aggressive" : gen_baseline_aggressive(n),
        "adaptive_fuzzing"    : gen_adaptive_fuzzing(n),
        "whitebox_adversarial": gen_whitebox_adversarial(n, model, scaler, ocsvm),
    }

    rows = []
    for name, samples in strategies.items():
        total = len(samples)
        if total == 0:
            continue

        # v1: IF only
        c1, _ = score_ensemble(samples, model, scaler, None)
        r1 = round(c1 / total * 100, 1)

        # v2: IF + OCSVM
        c2, _ = score_ensemble(samples, model, scaler, ocsvm)
        r2 = round(c2 / total * 100, 1)

        # v3: IF + OCSVM + RF
        if detector_rf is not None:
            c3, _ = score_triple(samples, model, scaler, ocsvm, detector_rf)
            r3 = round(c3 / total * 100, 1)
            gain = round(r3 - r2, 1)
        else:
            c3, r3, gain = "N/A", "N/A", "N/A"

        rows.append({
            "attack"        : name,
            "samples"       : total,
            "v1_IF_detected": c1,
            "v1_detect_%"   : r1,
            "v2_ens_detected": c2,
            "v2_detect_%"   : r2,
            "v3_tri_detected": c3,
            "v3_detect_%"   : r3,
            "gain_v2_to_v3" : gain,
        })

    # ── Print table ──────────────────────────────────────────────────────────
    print()
    print(f"  {'Attack':<22}{'N':>5}  {'v1(IF)':>9}  {'v2(+SVM)':>10}  {'v3(+RF)':>10}  {'Gain':>7}")
    print("  " + "-" * 68)
    for r in rows:
        print(
            f"  {r['attack']:<22}{r['samples']:>5}  "
            f"{str(r['v1_detect_%'])+' %':>9}  "
            f"{str(r['v2_detect_%'])+' %':>10}  "
            f"{str(r['v3_detect_%'])+' %':>10}  "
            f"{str(r['gain_v2_to_v3'])+(' pp' if r['gain_v2_to_v3'] != 'N/A' else ''):>7}"
        )
    print("  " + "-" * 68)
    print()

    # ── Save report ──────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(FINAL_DATASET), exist_ok=True)
    report_path = os.path.join(BASE_DIR, "data", "eval_report.csv")
    pd.DataFrame(rows).to_csv(report_path, index=False)
    print(f"  [+] Evaluation report saved -> {report_path}")
    print(f"  [+] Tip: Run python plots/attack_plots.py to visualise the results.\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Evaluate IDS detectors v1/v2/v3")
    ap.add_argument("-n", type=int, default=200, help="samples per attack strategy")
    args = ap.parse_args()
    main(n=args.n)
