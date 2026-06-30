from flask import Flask, request
import json

app = Flask(__name__)
last_detection = 0

def detect_attack(data):
    try:
        if (
            data["temperature"] < -40 or data["temperature"] > 80 or
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
    try:
        data = json.loads(request.data.decode())
        print("Received:", data)
        last_detection = detect_attack(data)
        print("Detection:", last_detection)
    except Exception as e:
        print("Error:", e)
        last_detection = 1
    return "OK", 200

@app.route("/feedback", methods=["GET"])
def feedback():
    return str(last_detection), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
