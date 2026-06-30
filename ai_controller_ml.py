import requests
import time
import random
import joblib
import numpy as np

ESP32_IP = "192.168.29.140"
KALI_IP = "192.168.29.64:8080"

ESP32_CMD = f"http://{ESP32_IP}/command"
FEEDBACK_URL = f"http://{KALI_IP}:8080/feedback"

model = joblib.load("ids_model.pkl")
scaler = joblib.load("scaler.pkl")

print("[*] Smart Adaptive Controller Started")

fuzz = 2
interval = 1000

success = 0
total = 0

def simulate_features(fuzz, interval):
    return [
        25 + random.uniform(-2, 4),
        60 + random.uniform(-3, 4),
        random.randint(0, 1),
        40 + random.uniform(-3, 6),
        80 + random.uniform(-2, 3),
        fuzz,
        interval
    ]

for i in range(50):

    candidates = []

    for _ in range(8):
        test_fuzz = random.randint(1, 3)
        test_interval = random.randint(400, 1200)

        features = simulate_features(test_fuzz, test_interval)

        X = scaler.transform([features])
        score = model.decision_function(X)[0]  

        candidates.append((test_fuzz, test_interval, score))

    
    fuzz, interval, score = max(candidates, key=lambda x: x[2])

    try:
        requests.get(ESP32_CMD, params={
            "fuzz": fuzz,
            "interval": interval
        })
    except:
        pass

    time.sleep(2)

    try:
        detected = int(requests.get(FEEDBACK_URL).text)
    except:
        detected = 1

    total += 1
    if detected == 0:
        success += 1

    print(f"[{i}] fuzz={fuzz}, interval={interval}, score={score:.4f}, detected={detected}")

    time.sleep(2)

print("\n=== RESULT ===")
print(f"Stealth Success Rate: {success/total*100:.2f}%")
