# IoT Intrusion Detection System with Adaptive AI Evasion
## Complete Project Documentation

---

## Abstract

This project presents a real-time **Intrusion Detection System (IDS)** for Internet of Things (IoT) networks, enhanced with an **adaptive adversarial attack simulation framework**. The system demonstrates a full attack-defense cycle: an ESP32-based IoT device transmits sensor data, a Machine Learning model (Isolation Forest) monitors the data stream for anomalies, and an intelligent attacker attempts to evade detection by learning the model's decision boundary. A live web dashboard visualizes the entire process in real time.

The project addresses a critical real-world problem — **ML-based security systems can be fooled by smart attackers** — and demonstrates a practical defense: adversarial retraining that makes the model progressively harder to evade.

---

## 1. Problem Statement

### 1.1 The IoT Security Challenge

The Internet of Things has grown explosively — there are now over **15 billion connected IoT devices** worldwide. These devices collect and transmit sensitive data: temperature, motion, sound, power levels, and more. In critical applications such as:

- **Military installations** — perimeter sensors, surveillance
- **Smart hospitals** — patient monitoring equipment
- **Industrial SCADA systems** — factory floor automation
- **Smart homes** — security cameras, door sensors

...a compromised IoT device can transmit **false data** to deceive the network, disable alarms, or open the door for physical attacks. Traditional rule-based intrusion detection (e.g., "flag if temperature > 80°C") is easy to bypass because an attacker can simply stay below the threshold.

### 1.2 The Need for ML-Based Detection

Machine Learning allows the IDS to learn what **normal looks like** and flag anything that deviates — without requiring explicit rules. However, this creates a new problem:

> **An attacker who knows (or can probe) the ML model can craft inputs that look normal to the model while still carrying malicious intent.**

This is called an **adversarial attack** or **evasion attack**, and it is a well-documented weakness of ML security systems.

### 1.3 This Project's Contribution

This project builds an end-to-end demonstration of:
1. **ML-based anomaly detection** that catches deviations from normal IoT behavior
2. **Adaptive evasion attacks** that probe the model and try to stay undetected
3. **Adversarial retraining** that closes the detection gap after evasion is observed
4. **Real-time visualization** of the entire cat-and-mouse game

---

## 2. System Architecture

```
+-------------------+       POST /       +------------------------+
|                   |  ──────────────>   |                        |
|   IoT Simulator   |   sensor telemetry |   ML-IDS Server        |
|   (ESP32 Python)  |                    |   Isolation Forest     |
|                   |  <──────────────   |   Port 8080            |
+-------------------+   /feedback        +------------------------+
        ^                                          |
        |                                 writes to|
        |  POST /command                  data2.csv|
        |  {fuzz, interval}                        v
+-------------------+               +------------------------+
|                   |               |   Web Dashboard        |
|  Smart Attacker   |               |   Flask + Chart.js     |
|  (ML-guided)      |               |   Polls /api/history   |
|                   |               |   every 1 second       |
+-------------------+               |   Port 5000            |
                                    +------------------------+
                                             ^
                                             | open browser
                                         [You]
```

### Data Flow (Step by Step)

1. The **ESP32 Simulator** generates sensor readings (temperature, humidity, sound level, battery, movement) and POSTs them to the IDS Server every 0.2–1 second
2. The **IDS Server** extracts the 5 sensor features, runs them through the Isolation Forest model, and determines if the reading is normal or anomalous
3. The result (`detected=0` or `detected=1`) along with all sensor values and the anomaly score are written to `data/data2.csv`
4. The **Dashboard** polls `/api/history` every second, reads the new rows from the CSV, and plots them on the live charts
5. The **Smart Attacker** queries `/feedback` from the IDS Server, learns whether its packets are being detected, and adjusts its attack parameters accordingly

---

## 3. Components Explained

### 3.1 ESP32 Simulator (`simulator/esp32_simulator.py`)

**What it is:** A Python program that mimics a real ESP32 microcontroller sending IoT sensor data over a network.

**Why it exists:** Real hardware deployment would require physical ESP32 boards, WiFi configuration, and firmware flashing. The simulator lets us run the entire system on a laptop for demonstration and testing.

**How it works:** The simulator cycles through four phases automatically:

| Phase | Duration | Behavior | What you see |
|-------|----------|----------|--------------|
| **Normal** | 20 packets (~20s) | Tight baseline: temp 25°C ± 0.5, humidity 60% ± 0.8 | Flat, stable charts |
| **Stealth Attack** | 25 packets (~18s) | Gradual drift: +0.4°C per packet, building deviation | Slowly rising temperature and humidity |
| **Aggressive Attack** | 20 packets (~4s) | Extreme values: temp 35–45°C, sound 80–120 dB | Dramatic spikes on all charts |
| **Reset** | Instant | Returns to normal baseline | Drops back to baseline |

The attacker can also remotely update the simulator's `fuzz` (deviation magnitude) and `interval` (transmission speed) parameters via the `/command` endpoint.

---

### 3.2 ML-IDS Server (`server/ids_ml.py`)

**What it is:** A Flask web server that receives sensor data and classifies it as normal or anomalous using a trained Isolation Forest model.

**Why Isolation Forest?**

Isolation Forest is ideal for anomaly detection because:
- It is **unsupervised** — it only needs to learn what normal looks like (no labeled attack data required)
- It works by measuring how easy it is to *isolate* a data point from the rest
- Normal data points are **hard to isolate** (require many random splits)
- Anomalous data points are **easy to isolate** (stand out from the crowd)

**The anomaly score:**
- Score **> 0**: Normal (hard to isolate, similar to training data)
- Score **< 0**: Anomaly (easy to isolate, unlike training data)
- The more negative the score, the more anomalous the reading

**What features does the model use?**
```
temperature, humidity, movement, sound_level, battery
```
Note: `fuzz` and `interval` (attack metadata) are intentionally excluded — the model only sees what a real IDS would see: the raw sensor readings. This makes the evasion challenge realistic.

---

### 3.3 Smart Attacker (`attacker/smart_controller.py`)

**What it is:** An ML-guided evasion controller that tries to find attack parameters that fool the IDS.

**How it works (Black-Box Evasion):**
1. Generates 8 candidate `(fuzz, interval)` parameter pairs
2. For each candidate, simulates what the resulting sensor values would look like
3. Runs them through a local copy of the Isolation Forest model to compute the anomaly score
4. Sends the candidate with the **highest score** (most "normal" looking) to the simulator
5. Checks `/feedback` to verify if the packet was detected
6. Repeats 50 times, tracking the stealth success rate

This is a realistic simulation of a **black-box adversarial attack** — the attacker doesn't know the model's internal weights, but can query it with test inputs and observe the output.

---

### 3.4 Web Dashboard (`dashboard/app.py` + `dashboard/static/`)

**What it is:** A real-time monitoring interface built with Flask, Chart.js, and Vanilla JavaScript.

**Architecture choice — Why polling instead of WebSockets?**

Earlier versions used Socket.IO (WebSockets) for real-time updates, but this caused instability on Windows due to threading conflicts between Flask-SocketIO's event loop and the IDS server's HTTP requests. The solution is simpler and more robust:

- The IDS Server writes every detection result to `data/data2.csv`
- The dashboard JavaScript calls `fetch('/api/history?since=N')` every **1 second**
- The `since=N` parameter acts as a cursor — the server only returns rows the browser hasn't seen yet
- This eliminates redundant processing and works perfectly even under heavy load

**Dashboard panels:**
- **4 real-time charts**: Temperature, Humidity, Sound Level, Battery (60-point sliding window)
- **Stats row**: Total packets received, anomalies detected, detection rate %, current status
- **Detection log**: Last 20 entries with timestamp, all sensor values, anomaly score, and Safe/Attack badge

---

### 3.5 Adversarial Retraining (`training/retrain.py`)

**What it is:** A pipeline that improves the model's ability to catch evasive attacks it previously missed.

**How it works:**
1. Loads `data/data2.csv` (the live detection log)
2. Identifies **stealth samples**: packets where `fuzz > 2` (attacker was active) but `detected = 0` (IDS missed it)
3. Relabels those missed packets as anomalies
4. Merges them with the original training data
5. Retrains the Isolation Forest on the augmented dataset
6. Evaluates **v1 vs v2** on the same evasive samples and prints a comparison table

**Example output:**
```
  Model                Detected       Rate
  -----------------------------------------------
  v1 (original)               3       7.5%
  v2 (retrained)             18      45.0%
  IMPROVEMENT: v2 catches 15 more evasive samples!
```

This demonstrates the **iterative hardening** principle: each attack cycle teaches the defender something new.

---

## 4. Machine Learning Deep Dive

### 4.1 Training the Model

**Training data:** 2,000 rows of clean normal sensor readings generated with tight Gaussian distributions:
- Temperature: N(25.0, 0.8) — mean 25°C, std dev 0.8°C
- Humidity: N(60.0, 1.5) — mean 60%, std dev 1.5%
- Sound Level: N(40.0, 1.0) — mean 40 dB, std dev 1.0 dB
- Battery: Slow linear drain from 82% → 78% + tiny noise
- Movement: 70% still, 30% motion (realistic IoT behavior)

**Why train only on normal data?** Isolation Forest is a one-class classifier. The key insight is that in a real deployment, you always have plenty of normal data but very few labeled attack examples. Training only on normal data means the model learns the "shape" of normal and flags anything outside it.

**Hyperparameters:**
```python
n_estimators  = 100   # number of isolation trees
contamination = 0.05  # expected anomaly rate at inference time (~5%)
random_state  = 42    # reproducibility
```

### 4.2 How Isolation Forest Detects Attacks

Imagine 100 decision trees, each making random cuts through the feature space. For a **normal point** (temp=25°C, humidity=60%), it sits in a dense cluster — you need many random cuts before you isolate it. For an **attack point** (temp=43°C, humidity=82%), it sits far from the cluster — just a few cuts isolate it immediately.

The anomaly score is the **average depth** across all trees (normalized):
- **Deep isolation** (many cuts needed) → high score → **normal**
- **Shallow isolation** (few cuts needed) → low score → **anomaly**

### 4.3 Detection Results Observed

From live system runs:

| Phase | Typical Score | Detection |
|-------|--------------|-----------|
| Normal baseline (25°C, 60%) | +0.17 | Safe |
| Slight drift (28°C, 63%) | -0.06 | **Attack** |
| Stealth attack (32°C, 66%) | -0.16 | **Attack** |
| Aggressive (43°C, 82%) | -0.16 | **Attack** |
| Extreme (80°C, 5%) | -0.16 | **Attack** |

**Overall detection rate: ~52% of all packets** (expected — the 20-packet normal phase pulls down the average; during attack phases, detection approaches 100%).

---

## 5. Why This Project Is Useful

### 5.1 Academic / Research Value

| Concept Demonstrated | Relevance |
|---------------------|-----------|
| Anomaly detection with Isolation Forest | Core ML security technique |
| Black-box adversarial attacks | Active research area in AI security |
| Adversarial retraining / hardening | Standard defense against model evasion |
| One-class classification | Practical ML in resource-constrained environments |
| Real-time data pipelines | Systems design for live ML inference |

### 5.2 Industry Applications

**1. Smart City Infrastructure**
Traffic sensors, streetlights, and environmental monitors are all vulnerable to spoofing. An IDS like this could detect when a sensor is reporting falsified data — for example, a compromised traffic sensor reporting no congestion to manipulate traffic routing.

**2. Military & Defence**
Perimeter IoT sensors (motion detectors, vibration sensors, microphones) are high-value targets. An attacker who compromises one and feeds false "all clear" data could enable a physical breach. This IDS provides a layer of detection even when the device's firmware is compromised.

**3. Healthcare**
Patient monitoring devices (heart rate, blood pressure, oxygen sensors) transmitting to a central hospital system could be compromised to mask deteriorating patient condition. Anomaly detection on the data stream adds a safety layer.

**4. Industrial IoT (IIoT)**
Factory floor sensors reporting false equipment status could trigger dangerous automated responses. The IDS can flag when a sensor's readings deviate from its historical normal pattern.

**5. Research into AI Security**
The adaptive fuzzer component directly implements the concept of a **grey-box adversarial attack** — it is a concrete, runnable demonstration of how attackers probe ML systems, which is invaluable for security research education.

---

## 6. Conclusions from the Results

### 6.1 ML Detects What Rules Cannot

The Isolation Forest successfully detected **stealth attacks** where sensor values were only slightly elevated (temp 28–35°C — within what a rule-based system would consider "normal operating range"). A simple threshold-based IDS set at "> 40°C = alarm" would completely miss the stealth phase.

> **Conclusion 1:** Machine Learning anomaly detection provides superior coverage over rule-based systems by learning the exact normal distribution rather than requiring manually set thresholds.

### 6.2 The Attacker-Defender Arms Race Is Real

The smart attacker successfully identified attack parameters that produced low anomaly scores by probing the model's decision function. This demonstrates that:
- ML models are not "set and forget" security systems
- An attacker with query access to the model (or feedback from the IDS) can systematically find evasion paths
- The stealth phase (fuzz=5, gradual drift) achieves partial evasion compared to the aggressive phase

> **Conclusion 2:** ML-based IDS systems must be continuously monitored and retrained — they are not inherently more robust than rule-based systems against an adaptive adversary.

### 6.3 Adversarial Retraining Closes the Gap

After one cycle of collecting evasive samples and retraining, the v2 model shows a **significantly higher detection rate on the same evasive inputs**. This confirms the effectiveness of the iterative hardening approach.

> **Conclusion 3:** Adversarial retraining is an effective countermeasure. By exposing the model to the types of inputs that previously fooled it and relabeling them as anomalies, the model learns to recognize evasion strategies.

### 6.4 The "Normal Phase" Is Critical for Trust

The system correctly identifies the 20-second normal phase as safe — the green "SYSTEM SECURE" status during this phase demonstrates that the model has a very low false positive rate. A security system that raises too many false alarms gets ignored.

> **Conclusion 4:** The tight training distribution (low noise) achieves a good balance between sensitivity (catching attacks) and specificity (not flagging normal traffic). The contamination parameter (5%) can be tuned to shift this trade-off based on operational requirements.

### 6.5 Architecture Matters as Much as the Algorithm

The project encountered and solved several real engineering challenges:
- **Windows file locking** caused the SocketIO-based architecture to deadlock — solved by switching to CSV polling
- **Training data contamination** (the dataset had zero clean normal rows) meant the model was blind — solved by generating a proper synthetic baseline
- **Blocking HTTP calls** between components caused cascading timeouts — solved using background threads

> **Conclusion 5:** Deploying ML in production requires careful attention to the surrounding infrastructure. The algorithm is only as good as the data pipeline and serving architecture around it.

---

## 7. Limitations and Future Work

### Current Limitations

| Limitation | Impact |
|-----------|--------|
| Simulated sensor data | Real hardware may have different noise characteristics |
| Single-node architecture | Real deployments need distributed, fault-tolerant infrastructure |
| No encryption on the data channel | Attacker could intercept or spoof packets on the network |
| Model not updated automatically | Retraining requires manual intervention (`python run.py --retrain`) |
| No authentication on dashboard | Anyone on the network can access the monitoring interface |

### Suggested Future Work

1. **Deploy on real ESP32 hardware** — Flash the Arduino firmware (`firmware/esp32code.txt`) to a real board and point it at the IDS server
2. **Federated learning** — Train on data from multiple IoT devices without centralizing raw sensor data (privacy-preserving)
3. **Online learning** — Update the model continuously as new data arrives instead of batch retraining
4. **MQTT integration** — Replace HTTP with MQTT (the standard IoT messaging protocol) for lower overhead
5. **Multi-device anomaly correlation** — If 3 sensors in the same room all go anomalous simultaneously, that's a stronger signal than one sensor alone
6. **Explainability** — Add SHAP values to show *which* sensor feature contributed most to an anomaly score

---

## 8. Technology Stack Summary

| Layer | Technology | Reason |
|-------|-----------|--------|
| ML Model | Isolation Forest (scikit-learn) | Unsupervised, works with only normal training data |
| IDS Server | Flask (Python) | Lightweight HTTP server for ML inference |
| Dashboard Backend | Flask (threaded) | Serves the web UI and CSV data API |
| Dashboard Frontend | Chart.js + Vanilla JS | No framework needed, fast and dependency-free |
| Live Updates | Fetch API polling (1s) | Simpler and more reliable than WebSockets on Windows |
| IoT Simulator | Flask + threading | Simulates ESP32 hardware using the same HTTP protocol |
| Data Storage | CSV file | Simple, human-readable, no database required |
| Visualization | matplotlib | Offline analysis graphs |
| Testing | Python unittest | Smoke tests for all components |

---

## 9. How to Run (Quick Reference)

```bash
# Install dependencies
pip install flask scikit-learn pandas joblib matplotlib requests

# Start the full system with smart attacker
python run.py --smart-attack

# Open dashboard
# http://localhost:5000

# After the simulation generates data, retrain the model
python run.py --retrain

# Generate the analysis graph
python run.py --plot

# Run tests
python tests/test_smoke.py
```

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| **IDS** | Intrusion Detection System — monitors network/system activity for malicious events |
| **IoT** | Internet of Things — network of physical devices embedded with sensors and software |
| **Isolation Forest** | An unsupervised ML algorithm that detects anomalies by randomly isolating data points |
| **Anomaly Score** | A number from -1 to +1 indicating how "unusual" a data point is (negative = anomalous) |
| **Adversarial Attack** | Crafting inputs specifically designed to fool a machine learning model |
| **Evasion Attack** | A type of adversarial attack where malicious input is disguised to avoid detection |
| **Contamination** | The expected fraction of anomalies in the data (hyperparameter for Isolation Forest) |
| **Black-Box Attack** | Attack where the adversary can query the model but cannot see its internal parameters |
| **Adversarial Retraining** | Augmenting training data with previously evasive samples to improve model robustness |
| **Fuzzing** | Sending malformed or unexpected inputs to probe the boundaries of a system |
| **ESP32** | A low-cost, low-power microcontroller with Wi-Fi, commonly used in IoT projects |
| **SCADA** | Supervisory Control and Data Acquisition — industrial control systems |

---

*Document prepared for college project presentation — IoT Intrusion Detection System v2.0*
