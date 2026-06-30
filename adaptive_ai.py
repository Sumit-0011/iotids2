
import requests
import time

ESP32_IP = "192.168.29.140"
KALI_IP = "192.168.29.64:8080"

ESP32_CMD = f"http://{ESP32_IP}/command"
FEEDBACK_URL = f"http://{KALI_IP}:8080/feedback"

fuzz = 1
interval = 1000

print("[*] Adaptive fuzzing started")

for i in range(40):

    try:
        detected = int(requests.get(FEEDBACK_URL).text)
    except:
        detected = 1

    if detected:
        # If detected → reduce aggressiveness
        fuzz = max(1, fuzz - 1)
        interval += 200
    else:
        # If NOT detected → increase aggressiveness
        fuzz = min(5, fuzz + 1)
        interval = max(300, interval - 100)

    try:
        requests.get(ESP32_CMD, params={"fuzz": fuzz, "interval": interval})
    except:
        pass

    print(f"[{i}] detected={detected}, fuzz={fuzz}, interval={interval}")
    time.sleep(2)

print("[*] Done")
