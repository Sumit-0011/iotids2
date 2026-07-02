"""
ML-based Intrusion Detection System Server.
Receives telemetry, runs a DUAL-DETECTOR ENSEMBLE (Isolation Forest + One-Class
SVM), explains each detection (XAI feature attribution), and logs to CSV.
The dashboard reads the CSV directly - no forwarding needed.

Two upgrades over the single-model version:
  1. Ensemble  - a packet is flagged if EITHER detector flags it (config
     ENSEMBLE_RULE). Two different model families are harder to evade than one.
  2. Explainability - for every packet we compute how far each sensor sits from
     the learned "normal" (a z-score from the scaler) and report which sensor
     contributed most to the anomaly, plus the full % breakdown.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

from flask import Flask, request, jsonify
import joblib
import csv
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

app = Flask(__name__)

model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
print("[IDS] Isolation Forest + scaler loaded OK")

# Second detector is optional: if ocsvm_model.pkl is missing we degrade
# gracefully to Isolation-Forest-only so the server always starts.
ocsvm = None
if os.path.exists(OCSVM_MODEL_PATH):
    ocsvm = joblib.load(OCSVM_MODEL_PATH)
    print("[IDS] One-Class SVM loaded OK - ensemble ACTIVE")
else:
    print(f"[IDS] One-Class SVM not found at {OCSVM_MODEL_PATH} - running "
          f"single-detector mode. Run: python training/train_ensemble.py")

last_detection = 0

# Short labels for the explainability breakdown, aligned to MODEL_FEATURES order.
FEATURE_LABELS = {
    "temperature": "temp",
    "humidity": "hum",
    "movement": "move",
    "sound_level": "sound",
    "battery": "batt",
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
        sensor = [
            float(data.get("temperature", 0)),
            float(data.get("humidity", 0)),
            int(data.get("movement", 0)),
            float(data.get("sound_level", 0)),
            float(data.get("battery", 0)),
        ]
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

        # ── Ensemble verdict ────────────────────────────────────────────
        if ENSEMBLE_RULE == "and":
            detected = 1 if (if_detected and svm_detected) else 0
        else:  # "or" (default): flag if either detector fires
            detected = 1 if (if_detected or svm_detected) else 0
        last_detection = detected

        # ── Explainability ──────────────────────────────────────────────
        top_feature, attribution, _ = explain(scaled_row)

        timestamp = datetime.now().strftime("%H:%M:%S")
        row = (
            [timestamp] + sensor + meta
            + [detected, score, if_detected, svm_detected, top_feature, attribution]
        )
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)

        return jsonify({
            "status": "ok",
            "detected": detected,
            "score": score,
            "iforest": if_detected,
            "ocsvm": svm_detected,
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
