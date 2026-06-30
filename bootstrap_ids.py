from flask import Flask, request
import json
import csv
import os

app = Flask(__name__)
last_detection = 0

# Create CSV with header
if not os.path.exists("training_data.csv"):
    with open("training_data.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "temperature",
            "humidity",
            "movement",
            "sound_level",
            "battery",
            "fuzz",
            "interval",
            "detected"
        ])

# Simple rule-based detection (temporary)
def detect(data):
    try:
        if (
            data["temperature"] > 80 or
            data["humidity"] > 100 or
            data["sound_level"] > 200 or
            data["battery"] < 0 or data["battery"] > 100
        ):
            return 1
    except:
        return 1
    return 0

@app.route("/", methods=["POST"])
def receive():
    global last_detection

    data = json.loads(request.data.decode())
    last_detection = detect(data)

    print("Received:", data)
    print("Detected:", last_detection)

    # SAVE DATA
    with open("training_data.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            data.get("temperature", 25),
            data.get("humidity", 60),
            data.get("movement", 0),
            data.get("sound_level", 40),
            data.get("battery", 80),
            data.get("fuzz", 1),
            data.get("interval", 1000),
            last_detection
        ])

    return "OK", 200

@app.route("/feedback", methods=["GET"])
def feedback():
    return str(last_detection), 200

app.run(host="0.0.0.0", port=8080)
