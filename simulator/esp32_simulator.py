import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import time
import threading
import requests
import random
from flask import Flask, request, jsonify

app = Flask(__name__)

# Attack state
state = {
    "fuzz": 0,
    "interval": 1000
}

@app.route("/command", methods=["POST"])
def command():
    data = request.json
    if "fuzz" in data:
        state["fuzz"] = int(data["fuzz"])
    if "interval" in data:
        state["interval"] = int(data["interval"])
    print(f"[*] Simulator updated: fuzz={state['fuzz']}, interval={state['interval']}")
    return jsonify({"status": "ok"})

def sender_loop():
    print(f"[*] Sender loop started -> target: {IDS_SERVER_URL}")
    counter = 0

    # Tight normal baseline — model was trained on this exact distribution
    b_temp  = 25.0
    b_hum   = 60.0
    b_sound = 40.0
    b_batt  = 80.0

    while True:
        counter += 1

        # Phase 1: NORMAL (20 packets at 1s each = ~20s)
        if counter < 20:
            fuzz     = 0
            interval = 1000
            temp  = b_temp  + random.gauss(0, 0.5)
            hum   = b_hum   + random.gauss(0, 0.8)
            sound = b_sound + random.gauss(0, 0.5)
            batt  = b_batt  - 0.01 * counter

        # Phase 2: STEALTH ATTACK (25 packets — gradual drift)
        elif counter < 45:
            fuzz     = state["fuzz"] if state["fuzz"] > 0 else 5
            interval = state["interval"] if state["interval"] < 1000 else 700
            # Gradually drift values away from normal — should trigger detection
            drift = (counter - 20) * 0.4        # grows 0 -> ~10
            temp  = b_temp  + drift + random.gauss(0, 1.0)
            hum   = b_hum   + drift + random.gauss(0, 1.5)
            sound = b_sound + drift * 1.5 + random.gauss(0, 1.0)
            batt  = b_batt  - 0.05 * counter

        # Phase 3: AGGRESSIVE ATTACK (20 packets — clearly anomalous)
        elif counter < 65:
            fuzz     = 15
            interval = 200
            # Extreme shifts — always detected
            temp  = b_temp  + random.uniform(10, 20)   # 35-45 C
            hum   = b_hum   + random.uniform(15, 25)   # 75-85 %
            sound = b_sound + random.uniform(40, 80)   # 80-120 dB
            batt  = b_batt  - random.uniform(5, 15)    # dropping fast

        # Phase 4: RESET back to normal
        else:
            counter  = 0
            fuzz     = 0
            interval = 1000
            temp  = b_temp  + random.gauss(0, 0.5)
            hum   = b_hum   + random.gauss(0, 0.8)
            sound = b_sound + random.gauss(0, 0.5)
            batt  = b_batt

        payload = {
            "device":      "military_compromised",
            "temperature": round(temp, 2),
            "humidity":    round(max(0, hum), 2),
            "movement":    random.choice([0, 1]),
            "sound_level": round(max(0, sound), 2),
            "battery":     round(max(0, min(100, batt)), 2),
            "fuzz":        fuzz,
            "interval":    interval
        }

        try:
            requests.post(IDS_SERVER_URL, json=payload, timeout=2)
        except Exception as e:
            print(f"[-] Failed to send: {e}")

        time.sleep(interval / 1000.0)

if __name__ == "__main__":
    t = threading.Thread(target=sender_loop, daemon=True)
    t.start()
    app.run(host=SIMULATOR_HOST, port=SIMULATOR_PORT)
