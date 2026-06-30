from flask import Flask, request
import json
import joblib
import numpy as np
import csv
import os

app = Flask(__name__)

model = joblib.load("ids_model.pkl")
scaler = joblib.load("scaler.pkl")

last_detection = 0
LOG_FILE = "data2.csv"

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "temperature","humidity","movement",
            "sound_level","battery","fuzz","interval","detected"
        ])

@app.route("/", methods=["POST"])
def receive():
    global last_detection

    try:
        data = json.loads(request.data.decode())

        features = [
            data.get("temperature", 25),
            data.get("humidity", 60),
            data.get("movement", 0),
            data.get("sound_level", 40),
            data.get("battery", 80),
            data.get("fuzz", 1),
            data.get("interval", 1000)
        ]

        X = scaler.transform([features])

       
        pred = model.predict(X)[0]  # -1 or 1
        score = model.decision_function(X)[0]

        last_detection = 1 if pred == -1 else 0

        print("\nReceived:", data)
        print("Detection:", last_detection)
        print("Score:", score)

        with open(LOG_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(features + [last_detection])

    except Exception as e:
        print("Error:", e)
        last_detection = 1

    return "OK", 200


@app.route("/feedback")
def feedback():
    return str(last_detection)

app.run(host="0.0.0.0", port=8080)
