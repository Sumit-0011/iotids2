import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

from flask import Flask, request, jsonify
import csv
import requests
from datetime import datetime

app = Flask(__name__)

last_detection = 0

# Same schema as ids_ml.py for consistency: timestamp, features, detected, score.
# Rule-based IDS doesn't have a decision score, so we use a dummy 0.0.
CSV_COLUMNS = ["timestamp"] + FEATURE_COLUMNS + ["detected", "score"]

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)

@app.route("/", methods=["POST"])
def receive():
    global last_detection
    data = request.json
    try:
        temp = float(data.get("temperature", 0))
        hum = float(data.get("humidity", 0))
        sound = float(data.get("sound_level", 0))
        batt = float(data.get("battery", 0))
        
        detected = 1 if (temp < -40 or temp > 80 or hum > 100 or sound > 200 or batt < 0 or batt > 100) else 0
        last_detection = detected
        
        features = [
            temp, hum, int(data.get("movement", 0)), sound, batt,
            int(data.get("fuzz", 0)), int(data.get("interval", 0))
        ]
        
        ts = datetime.now().strftime("%H:%M:%S")
        score = 0.0  # Rule-based IDS has no decision score; use placeholder.
        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([ts] + features + [detected, score])
            
        try:
            requests.post(DASHBOARD_URL + "/api/telemetry", json=data, timeout=1)
        except:
            pass
            
        return jsonify({"status": "ok", "detected": detected})
    except (ValueError, KeyError, TypeError) as e:
        print(f"[ERROR] Invalid telemetry format: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": f"Invalid data format: {str(e)}"}), 400
    except IOError as e:
        print(f"[ERROR] CSV write failed: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": "Logging failed"}), 500
    except Exception as e:
        print(f"[ERROR] Unexpected error in rule-based IDS: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/feedback", methods=["GET"])
def feedback():
    return str(last_detection)

if __name__ == "__main__":
    app.run(host=IDS_SERVER_HOST, port=IDS_SERVER_PORT)
