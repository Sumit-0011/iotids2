"""
ML-based Intrusion Detection System Server.
Receives telemetry, runs a TRIPLE-DETECTOR ENSEMBLE:
  1. Isolation Forest  — unsupervised, one-class, tree-based
  2. One-Class SVM     — unsupervised, kernel boundary
  3. Adversarial RF    — supervised RandomForest hardened against evasion attacks

A packet is flagged if ANY detector fires (ENSEMBLE_RULE = 'or').
Also explains each detection via XAI feature attribution (z-score based).
The dashboard reads the CSV log directly — no WebSocket needed.

Graceful degradation:
  - If ocsvm_model.pkl is missing  → dual-detector (IF + RF)
  - If detector.pkl is missing     → dual-detector (IF + OCSVM)
  - If both are missing            → single-detector (IF only)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

from flask import Flask, request, jsonify
import joblib
import csv
import pandas as pd
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

app = Flask(__name__)

model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
print("[IDS] Isolation Forest + scaler loaded OK")

# Second detector (One-Class SVM) is optional — degrade gracefully if absent.
ocsvm = None
if os.path.exists(OCSVM_MODEL_PATH):
    ocsvm = joblib.load(OCSVM_MODEL_PATH)
    print("[IDS] One-Class SVM loaded OK")
else:
    print(f"[IDS] One-Class SVM not found at {OCSVM_MODEL_PATH} — skipping."
          f" Run: python training/train_ensemble.py")

# Third detector (Supervised Adversarial RandomForest) is also optional.
# It is trained on RAW sensor features — no scaling needed.
detector_rf = None
if os.path.exists(DETECTOR_MODEL_PATH):
    detector_rf = joblib.load(DETECTOR_MODEL_PATH)
    print("[IDS] Supervised Detector (RF) loaded OK — triple-detector ensemble ACTIVE")
else:
    print(f"[IDS] Supervised Detector not found at {DETECTOR_MODEL_PATH} — skipping."
          f" Run: python training/train_detector.py")

last_detection = 0

# Short labels for the explainability breakdown, aligned to MODEL_FEATURES order.
FEATURE_LABELS = {
    "temperature": "temp",
    "pressure": "press",
    "humidity": "hum",
}

# CSV schema now carries the ensemble verdicts and the explainability columns.
CSV_COLUMNS = LOG_COLUMNS

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
# Rewrite the header if the file is missing, empty, or still on the old schema.
_needs_header = True
if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
    with open(LOG_FILE, "r", newline="") as f:
        _needs_header = f.readline().strip().split(",") != CSV_COLUMNS
if _needs_header:
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)


def explain(scaled_row):
    """
    Explainable-AI attribution using the scaler's z-scores.

    StandardScaler maps each feature to (x - mean) / std, so the absolute scaled
    value IS the number of standard deviations that sensor is from normal. The
    bigger |z|, the more that sensor drove the anomaly. We normalize the |z|
    values into percentages so the dashboard can show "temperature = 78% of the
    reason this looked like an attack".

    Returns (top_feature_label, "temp:78|sound:15|...", {label: percent}).
    """
    z = [abs(v) for v in scaled_row]
    total = sum(z)
    if total == 0:
        return "none", "", {}

    contrib = {}
    for feat, zval in zip(MODEL_FEATURES, z):
        contrib[FEATURE_LABELS[feat]] = round(zval / total * 100)

    # Sort features by contribution, highest first.
    ordered = sorted(contrib.items(), key=lambda kv: kv[1], reverse=True)
    top_feature = ordered[0][0]
    attribution = "|".join(f"{label}:{pct}" for label, pct in ordered)
    return top_feature, attribution, contrib


@app.route("/", methods=["POST"])
def receive():
    global last_detection
    data = request.json
    try:
        # Genuine sensor readings - the only thing the models are allowed to see.
        sensor = [float(data.get(f, 0)) for f in MODEL_FEATURES]
        # Attack-control metadata - logged for analysis, never fed to the models.
        meta = [
            int(data.get("fuzz", 0)),
            int(data.get("interval", 0)),
        ]

        scaled = scaler.transform([sensor])
        scaled_row = scaled[0]

        # ── Detector 1: Isolation Forest ────────────────────────────────
        if_detected = 1 if model.predict(scaled)[0] == -1 else 0
        # Raw Isolation Forest score (negative = more anomalous). Kept as the
        # headline "score" for backward compatibility with the dashboard/plots.
        score = round(float(model.decision_function(scaled)[0]), 4)

        # ── Detector 2: One-Class SVM (optional) ────────────────────────
        if ocsvm is not None:
            svm_detected = 1 if ocsvm.predict(scaled)[0] == -1 else 0
        else:
            svm_detected = if_detected  # mirror IF when the 2nd model is absent

        # ── Detector 3: Supervised Adversarial RF (optional) ────────────
        # The RF was trained on raw (unscaled) sensor features, so we feed
        # it the raw `sensor` list wrapped in a DataFrame.
        if detector_rf is not None:
            raw_df = pd.DataFrame([sensor], columns=MODEL_FEATURES)
            det_pred = detector_rf.predict(raw_df)[0]
            # RF labels: 1 = attack, 0 = normal (supervised convention)
            rf_detected = 1 if int(det_pred) == 1 else 0
        else:
            rf_detected = 0  # absent → abstain (don't inflate false-positives)

        # ── Ensemble verdict ────────────────────────────────────────────
        votes = [if_detected, svm_detected, rf_detected]
        if ENSEMBLE_RULE == "and":
            detected = 1 if all(votes) else 0
        else:  # "or" (default): flag if any detector fires
            detected = 1 if any(votes) else 0
        last_detection = detected

        # ── Explainability ──────────────────────────────────────────────
        top_feature, attribution, _ = explain(scaled_row)

        timestamp = datetime.now().strftime("%H:%M:%S")
        row = (
            [timestamp] + sensor + meta
            + [detected, score, if_detected, svm_detected, rf_detected,
               top_feature, attribution]
        )
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        # ── Ground truth (from TON_IoT dataset, if provided) ────────────
        gt_label = data.get("ground_truth_label")       # 0=normal, 1=attack
        gt_type  = data.get("ground_truth_type", "")     # normal/injection/backdoor/ddos

        # Terminal output for the CLI monitor
        gt_str = ""
        if gt_label is not None:
            gt_tag = f"{gt_type.upper()}" if int(gt_label) == 1 else "NORMAL"
            # Check if our detection matches the ground truth
            correct = (detected == int(gt_label))
            if correct:
                accuracy_icon = "\033[92mOK\033[0m"  # green OK
            else:
                accuracy_icon = "\033[93mMISS\033[0m"  # yellow MISS (mismatch)
            gt_str = f" | Truth: {gt_tag:<10s} {accuracy_icon}"

        if detected:
            print(f"[\033[91m!\033[0m] \033[91mATTACK DETECTED\033[0m | Temp: {sensor[0]:.1f}C | Press: {sensor[1]:.1f}hPa | Hum: {sensor[2]:.1f}% | Cause: {attribution}{gt_str}")
        else:
            print(f"[\033[92m+\033[0m] SAFE            | Temp: {sensor[0]:.1f}C | Press: {sensor[1]:.1f}hPa | Hum: {sensor[2]:.1f}%{gt_str}")

        return jsonify({
            "status": "ok",
            "detected": detected,
            "score": score,
            "iforest": if_detected,
            "ocsvm": svm_detected,
            "detector": rf_detected,
            "top_feature": top_feature,
            "attribution": attribution,
        })
    except (ValueError, KeyError, TypeError) as e:
        print(f"[ERROR] Invalid telemetry format: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": f"Invalid data format: {str(e)}"}), 400
    except IOError as e:
        print(f"[ERROR] CSV write failed: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": "Logging failed"}), 500
    except Exception as e:
        print(f"[ERROR] Unexpected error in IDS: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/feedback", methods=["GET"])
def feedback():
    return str(last_detection)

if __name__ == "__main__":
    print(f"[IDS] http://localhost:{IDS_SERVER_PORT}")
    app.run(host=IDS_SERVER_HOST, port=IDS_SERVER_PORT, threaded=True)
