import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import time
import threading
import requests
import pandas as pd
from flask import Flask, request, jsonify

app = Flask(__name__)

# Attack state (legacy)
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
    # Prefer the labeled TON_IoT dataset for rich terminal output;
    # fall back to the preprocessed live_traffic.csv if it's missing.
    ton_iot_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ton_iot_weather.csv')
    if os.path.exists(ton_iot_path):
        dataset_path = ton_iot_path
        use_ton_iot = True
    else:
        dataset_path = LIVE_TRAFFIC
        use_ton_iot = False

    print(f"[*] Sender loop started -> target: {IDS_SERVER_URL}")
    print(f"[*] Streaming {'TON_IoT Weather' if use_ton_iot else 'live traffic'} from {dataset_path}")
    
    # Wait for IDS to be up
    time.sleep(2)
    
    while True:
        try:
            df = pd.read_csv(dataset_path)
        except Exception as e:
            print(f"[-] Could not read {dataset_path}: {e}")
            time.sleep(5)
            continue
            
        for _, row in df.iterrows():
            payload = {
                "device": "weather_sensor_01",
                "temperature": round(row.get('temperature', 25.0), 2),
                "pressure": round(row.get('pressure', 1013.25), 2),
                "humidity": round(row.get('humidity', 60.0), 2),
                "fuzz": state["fuzz"] if state["fuzz"] > 0 else int(row.get('fuzz', 0)),
                "interval": state["interval"] if state["interval"] < 1000 else int(row.get('interval', 1000)),
            }

            # Include ground-truth label and attack type if available
            if use_ton_iot:
                payload["ground_truth_label"] = int(row.get('label', 0))
                payload["ground_truth_type"] = str(row.get('type', 'normal'))

            try:
                requests.post(IDS_SERVER_URL, json=payload, timeout=2)
            except Exception as e:
                print(f"[-] Failed to send: {e}")
            
            # Use the interval from state, or default to 1000ms
            interval = state["interval"] if state["interval"] < 1000 else 1000
            time.sleep(interval / 1000.0)
            
        print("[*] Reached end of dataset, looping...")


if __name__ == "__main__":
    t = threading.Thread(target=sender_loop, daemon=True)
    t.start()
    app.run(host=SIMULATOR_HOST, port=SIMULATOR_PORT)
