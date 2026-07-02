import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import time
import random
import requests

# Sensor baselines the compromised device reports around.
BASELINES = {"temperature": 25.0, "humidity": 60.0, "sound_level": 40.0, "battery": 80.0}


def craft_payload(fuzz, interval):
    """Build a telemetry packet jittered by `fuzz` around the sensor baselines."""
    return {
        "device": "attacker_probe",
        "temperature": round(BASELINES["temperature"] + random.uniform(-fuzz, fuzz), 2),
        "humidity": round(BASELINES["humidity"] + random.uniform(-fuzz, fuzz), 2),
        "movement": random.choice([0, 1]),
        "sound_level": round(BASELINES["sound_level"] + random.uniform(-fuzz, fuzz), 2),
        "battery": round(BASELINES["battery"], 2),
        "fuzz": fuzz,
        "interval": interval,
    }


def run_fuzzer():
    print("[*] Starting adaptive fuzzer...")
    fuzz = 1
    interval = 1000

    for i in range(40):
        # Send our own probe and read the verdict for THIS packet from the
        # response - no more racing the simulator's traffic via /feedback.
        payload = craft_payload(fuzz, interval)
        try:
            r = requests.post(IDS_SERVER_URL, json=payload, timeout=2)
            detected = int(r.json().get("detected", 0))
        except requests.RequestException as e:
            print(f"[!] IDS unreachable (attempt {i+1}): {e}")
            detected = 0
        except (ValueError, KeyError) as e:
            print(f"[!] Malformed IDS response (attempt {i+1}): {e}")
            detected = 0

        if detected == 1:
            print(f"[+] Detected (fuzz={fuzz})! Reducing aggressiveness...")
            fuzz = max(1, fuzz - 1)
            interval += 100
        else:
            print(f"[-] Undetected (fuzz={fuzz}). Increasing aggressiveness...")
            fuzz += 1
            interval = max(100, interval - 50)

        time.sleep(1)


if __name__ == "__main__":
    run_fuzzer()
