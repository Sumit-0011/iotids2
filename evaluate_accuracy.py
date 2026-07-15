"""
IoT IDS — Model Accuracy Evaluation
=====================================
Evaluates the Triple-Detector Ensemble against the TON_IoT Weather dataset.
Prints standard ML metrics: Accuracy, Precision, Recall, F1-Score,
Confusion Matrix, and per-attack-type detection rates.

Usage:
    python evaluate_accuracy.py
"""
import sys, os
import pandas as pd
import numpy as np
import joblib

sys.path.insert(0, os.path.dirname(__file__))
from config import (
    MODEL_FEATURES, MODEL_PATH, SCALER_PATH,
    OCSVM_MODEL_PATH, DETECTOR_MODEL_PATH, ENSEMBLE_RULE,
)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TON_IOT_PATH = os.path.join(BASE_DIR, "data", "ton_iot_weather.csv")
FINAL_DATASET = os.path.join(BASE_DIR, "data", "final_dataset.csv")


def load_models():
    """Load all available detectors."""
    print("[*] Loading models...")
    scaler = joblib.load(SCALER_PATH)
    iforest = joblib.load(MODEL_PATH)
    print("    Isolation Forest + Scaler  OK")

    ocsvm = None
    if os.path.exists(OCSVM_MODEL_PATH):
        ocsvm = joblib.load(OCSVM_MODEL_PATH)
        print("    One-Class SVM              OK")
    else:
        print("    One-Class SVM              MISSING (skipped)")

    detector_rf = None
    if os.path.exists(DETECTOR_MODEL_PATH):
        detector_rf = joblib.load(DETECTOR_MODEL_PATH)
        print("    Adversarial RF             OK")
    else:
        print("    Adversarial RF             MISSING (skipped)")

    return scaler, iforest, ocsvm, detector_rf


def predict_ensemble(X, scaler, iforest, ocsvm, detector_rf):
    """Run all detectors and return per-detector + ensemble predictions."""
    X_scaled = scaler.transform(X)

    # Detector 1: Isolation Forest
    if_preds = np.array([1 if p == -1 else 0 for p in iforest.predict(X_scaled)])

    # Detector 2: One-Class SVM
    if ocsvm is not None:
        svm_preds = np.array([1 if p == -1 else 0 for p in ocsvm.predict(X_scaled)])
    else:
        svm_preds = if_preds.copy()

    # Detector 3: Supervised Adversarial RF (uses raw features, no scaling)
    if detector_rf is not None:
        rf_preds = np.array([1 if int(p) == 1 else 0 for p in detector_rf.predict(
            pd.DataFrame(X, columns=MODEL_FEATURES)
        )])
    else:
        rf_preds = np.zeros_like(if_preds)

    # Ensemble
    votes = np.stack([if_preds, svm_preds, rf_preds], axis=1)
    if ENSEMBLE_RULE == "and":
        ensemble = np.all(votes, axis=1).astype(int)
    else:  # "or"
        ensemble = np.any(votes, axis=1).astype(int)

    return if_preds, svm_preds, rf_preds, ensemble


def confusion_matrix_manual(y_true, y_pred):
    """Compute TP, TN, FP, FN."""
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    return tp, tn, fp, fn


def print_metrics(name, y_true, y_pred):
    """Print accuracy, precision, recall, F1 for a single detector."""
    tp, tn, fp, fn = confusion_matrix_manual(y_true, y_pred)
    total = len(y_true)
    accuracy  = (tp + tn) / total * 100 if total > 0 else 0
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"  {name:<28s}  Acc: {accuracy:5.1f}%  Prec: {precision:5.1f}%  Rec: {recall:5.1f}%  F1: {f1:5.1f}%")
    return accuracy, precision, recall, f1, tp, tn, fp, fn


def evaluate():
    # ── Load dataset ─────────────────────────────────────────────────────
    if os.path.exists(TON_IOT_PATH):
        df = pd.read_csv(TON_IOT_PATH)
        y_true = df["label"].values
        attack_types = df["type"].values
        dataset_name = "TON_IoT Weather (ton_iot_weather.csv)"
    else:
        df = pd.read_csv(FINAL_DATASET)
        y_true = df["detected"].values
        attack_types = None
        dataset_name = "final_dataset.csv"

    X = df[MODEL_FEATURES].values
    print(f"[*] Dataset: {dataset_name}")
    print(f"    Total samples: {len(df)}  |  Normal: {(y_true==0).sum()}  |  Attack: {(y_true==1).sum()}")
    print()

    # ── Load models & predict ────────────────────────────────────────────
    scaler, iforest, ocsvm, detector_rf = load_models()
    print()
    if_preds, svm_preds, rf_preds, ensemble = predict_ensemble(
        X, scaler, iforest, ocsvm, detector_rf
    )

    # ── Per-detector metrics ─────────────────────────────────────────────
    print("=" * 80)
    print("  DETECTOR PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"  {'Detector':<28s}  {'Acc':>5s}    {'Prec':>5s}    {'Rec':>5s}    {'F1':>5s}")
    print("-" * 80)

    print_metrics("Isolation Forest", y_true, if_preds)
    if ocsvm is not None:
        print_metrics("One-Class SVM", y_true, svm_preds)
    if detector_rf is not None:
        print_metrics("Adversarial RF", y_true, rf_preds)

    print("-" * 80)
    _, _, _, _, tp, tn, fp, fn = print_metrics(
        f"ENSEMBLE ({ENSEMBLE_RULE.upper()} vote)", y_true, ensemble
    )
    print("=" * 80)

    # ── Confusion Matrix ─────────────────────────────────────────────────
    print()
    print("  CONFUSION MATRIX (Ensemble)")
    print("  " + "-" * 36)
    print(f"                     Predicted")
    print(f"                   Safe    Attack")
    print(f"  Actual Safe    {tn:>5}     {fp:>5}   (FP = {fp})")
    print(f"  Actual Attack  {fn:>5}     {tp:>5}   (FN = {fn})")
    print("  " + "-" * 36)
    print()

    # ── Per-attack-type breakdown ────────────────────────────────────────
    if attack_types is not None:
        unique_types = [t for t in ['normal', 'injection', 'backdoor', 'ddos']
                        if t in set(attack_types)]
        print("  PER-ATTACK-TYPE DETECTION RATES")
        print("  " + "-" * 50)
        print(f"  {'Type':<12s}  {'Total':>6s}  {'Detected':>8s}  {'Missed':>7s}  {'Rate':>7s}")
        print("  " + "-" * 50)

        for atype in unique_types:
            mask = (attack_types == atype)
            total_t = int(mask.sum())
            if atype == "normal":
                # For normal, "detected" means false positive
                flagged = int(ensemble[mask].sum())
                missed = total_t - flagged
                rate = (total_t - flagged) / total_t * 100  # correctly classified
                print(f"  {'NORMAL':<12s}  {total_t:>6d}  {total_t - flagged:>8d}  {flagged:>7d}  {rate:>6.1f}%  (correctly safe)")
            else:
                caught = int(ensemble[mask].sum())
                missed = total_t - caught
                rate = caught / total_t * 100
                print(f"  {atype.upper():<12s}  {total_t:>6d}  {caught:>8d}  {missed:>7d}  {rate:>6.1f}%")

        print("  " + "-" * 50)

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    total = len(y_true)
    overall_acc = (tp + tn) / total * 100
    attack_recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0

    print(f"  SUMMARY")
    print(f"  Overall Accuracy:       {overall_acc:.1f}%")
    print(f"  Attack Detection Rate:  {attack_recall:.1f}%  ({tp}/{tp+fn} attacks caught)")
    print(f"  False Positive Rate:    {fpr:.1f}%  ({fp}/{fp+tn} normal flagged)")
    print()


if __name__ == "__main__":
    evaluate()
