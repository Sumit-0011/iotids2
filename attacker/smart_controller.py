import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import time
import requests
import joblib
import random
import warnings
warnings.filterwarnings("ignore")


def run_smart_controller():
    print("[*] Starting ML-guided evasion controller...")
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    b_temp = 25.0
    b_press = 1013.25
    b_hum = 60.0

    successes = 0
    total = 0

    for i in range(50):
        best_score = -float('inf')
        best_payload = None

        # Search candidate perturbations and keep the one the model rates most "normal".
        for _ in range(8):
            cand_fuzz = random.randint(1, 8)
            cand_int = random.randint(200, 1500)

            cand_temp = b_temp + random.uniform(-cand_fuzz, cand_fuzz)
            cand_press = b_press + random.uniform(-cand_fuzz, cand_fuzz)
            cand_hum = b_hum + random.uniform(-cand_fuzz, cand_fuzz)

            # Only the 3 sensor features are scored
            features = [[cand_temp, cand_press, cand_hum]]
            scaled = scaler.transform(features)
            score = model.decision_function(scaled)[0]

            if score > best_score:
                best_score = score
                best_payload = {
                    "device": "attacker_smart",
                    "temperature": round(cand_temp, 2),
                    "pressure": round(cand_press, 2),
                    "humidity": round(cand_hum, 2),
                    "fuzz": cand_fuzz,
                    "interval": cand_int,
                }

        # Send the exact packet we optimized and read whether IT evaded detection.
        detected = 0
        try:
            r = requests.post(IDS_SERVER_URL, json=best_payload, timeout=2)
            detected = int(r.json().get("detected", 0))
            total += 1
            if detected == 0:
                successes += 1
        except requests.RequestException as e:
            print(f"[!] IDS unreachable (iteration {i+1}): {e}")
        except (ValueError, KeyError) as e:
            print(f"[!] Malformed IDS response (iteration {i+1}): {e}")

        print(f"[*] Iteration {i+1} -> score: {best_score:.4f}, detected: {detected}, "
              f"fuzz: {best_payload['fuzz']}")
        time.sleep(1)

    print(f"\n[+] Stealth rate: {successes}/{total} ({(successes/max(1, total))*100:.1f}%)")


if __name__ == "__main__":
    run_smart_controller()
