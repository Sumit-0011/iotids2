# IoT Intrusion Detection System (IDS) with Adaptive AI Evasion

> **ML-based anomaly detection for IoT sensor networks** — with an adaptive fuzzing framework that demonstrates how attackers can evade machine learning defenses, and how adversarial retraining can close the gap.

---

## Architecture

```
+------------------+   POST /    +------------------------+
|                  | ----------> |                        |
|  IoT Simulator   |             |   IDS Server (ML)      |
|  (Python ESP32)  |             |   Isolation Forest     |
|                  | <-- /cmd -- |                        |
+------------------+             +------------------------+
        ^                                  |
        |                        writes to |
        |                       data2.csv  |
        |                                  v
        |  fuzz/interval        +------------------------+
        +-- Adaptive/Smart --   |   Web Dashboard        |
            Attacker            |   Polls /api/history   |
                                |   every 1 second       |
                                +------------------------+
```

**How it works:**
1. The **ESP32 Simulator** generates sensor telemetry (temperature, humidity, sound, battery) and POSTs it to the IDS Server every 0.2 – 1 second
2. The **IDS Server** runs the data through an Isolation Forest model using only genuine sensor features (fuzz/interval are logged as metadata, never fed to the model), flags anomalies, and writes every result row to `data/data2.csv`
3. The **Adaptive Attacker** crafts its own telemetry, POSTs it directly to the IDS Server, and reads the `detected` verdict from the response to adapt its `fuzz` and `interval` attack parameters in real-time
4. The **Dashboard** simply polls `/api/history` every second and plots whatever is in `data2.csv` — no WebSockets required

---

## Project Structure

```
iotids2/
├── run.py                      # Unified launcher
├── config.py                   # All ports, paths, and parameters
├── requirements.txt            # Python dependencies
├── README.md
│
├── server/
│   ├── ids_ml.py               # ML IDS (Isolation Forest)
│   └── ids_rule.py             # Rule-based IDS (thresholds)
│
├── attacker/
│   ├── adaptive_fuzzer.py      # Feedback-driven fuzzer
│   └── smart_controller.py     # ML-guided evasion controller
│
├── simulator/
│   └── esp32_simulator.py      # Python ESP32 simulator
│
├── dashboard/
│   ├── app.py                  # Flask backend (read-only, serves CSV data)
│   ├── templates/index.html    # Dashboard HTML
│   └── static/
│       ├── style.css           # Dark cybersecurity theme
│       ├── dashboard.js        # Chart.js + 1s polling (no SocketIO)
│       └── chart.min.js        # Chart.js (bundled locally)
│
├── training/
│   ├── train_model.py          # Train Isolation Forest from scratch
│   ├── merge_data.py           # Merge training datasets
│   └── retrain.py              # Adversarial retraining + v1 vs v2 evaluation
│
├── models/
│   ├── ids_model.pkl           # Active Isolation Forest model
│   ├── scaler.pkl              # Active StandardScaler
│   ├── ids_model_v2.pkl        # Retrained model (after running retrain.py)
│   └── scaler_v2.pkl
│
├── data/
│   ├── data2.csv               # Live detection log (written by IDS, read by dashboard)
│   ├── final_dataset.csv       # Merged training dataset
│   ├── training_data.csv       # Bootstrap training data
│   └── live_traffic.csv        # Captured live traffic
│
├── plots/
│   └── plot_graph.py           # Generate analysis graphs from data2.csv
│
└── firmware/
    └── esp32code.txt           # Original Arduino sketch (reference)
```

---

## Quick Start

### Prerequisites
- Python 3.8+

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run the full system (IDS + Simulator + Dashboard)
```bash
python run.py
```

Then open **http://localhost:5000** in your browser. The dashboard polls the data every second — no refresh needed.

### Run with attack simulation
```bash
# Simple adaptive fuzzer
python run.py --attack

# ML-guided smart attacker (recommended for demo)
python run.py --smart-attack
```

### Run each component manually (4 separate terminals)
```bash
# Terminal 1: Dashboard
python dashboard/app.py

# Terminal 2: IDS Server
python server/ids_ml.py

# Terminal 3: Simulator
python simulator/esp32_simulator.py

# Terminal 4: Attacker (optional)
python attacker/smart_controller.py
```

---

## Launcher Options

| Command | Description |
|---------|-------------|
| `python run.py` | Start IDS + Simulator + Dashboard |
| `python run.py --attack` | Also start simple adaptive fuzzer |
| `python run.py --smart-attack` | Also start ML-guided attacker |
| `python run.py --rule-based` | Use threshold-based IDS instead of ML |
| `python run.py --no-dashboard` | Skip web dashboard |
| `python run.py --retrain` | Run adversarial retraining pipeline |
| `python run.py --plot` | Generate analysis graphs |

---

## Presentation Demo Script

### Step 1 — Start the system
```bash
python run.py --smart-attack
```
Open **http://localhost:5000**

### Step 2 — Explain the Normal Phase
For the first ~15 seconds, the simulator sends normal baseline traffic. The dashboard shows all-green "Safe" readings.

### Step 3 — Watch the Stealth Attack
The smart controller begins slowly drifting sensor values. Demonstrate how the Isolation Forest initially misses these because they look "almost normal."

### Step 4 — Aggressive Phase Detection
As the attack escalates, anomaly scores drop and the dashboard flips to red — "ATTACK DETECTED."

### Step 5 — Adversarial Retraining (Defense-in-Depth)
```bash
python run.py --retrain
```
Show the evaluation table comparing v1 vs v2 detection rates on previously-evasive samples.

### Step 6 — Visualization
```bash
python run.py --plot
```
Open `plots/final_graph.png` — shows the 4-panel sensor analysis with attack phase highlighted in red.

---

## How It Works

### Dashboard Architecture (CSV Polling)
The dashboard uses a dead-simple, rock-solid approach:
- The IDS Server appends each result row to `data/data2.csv`
- The Flask dashboard serves `/api/history` which reads the tail of that CSV
- The browser JS calls `fetch('/api/history')` every **1 second** and plots new rows
- **No WebSockets, no SocketIO, no external CDN dependencies** — everything is served locally

### Isolation Forest Detection
The IDS uses scikit-learn's Isolation Forest, which detects anomalies by measuring how easily a data point can be "isolated" from the training distribution:
- **Normal data** — requires many splits to isolate → **high score (positive)**
- **Anomalous data** — isolated quickly → **low score (negative → flagged)**

The model is trained **exclusively on genuine sensor features** (temperature, humidity, movement, sound_level, battery). Attacker control parameters (`fuzz`, `interval`) are logged for analysis but **never fed to the model**, ensuring detection is based on actual sensor anomalies, not metadata leakage.

### Adaptive Evasion Strategies
| Controller | Strategy |
|------------|----------|
| `adaptive_fuzzer.py` | Real-time feedback loop — sends each probe directly to IDS, reads `detected` from response, escalates `fuzz` if undetected, reduces if caught |
| `smart_controller.py` | White-box guided evasion — loads local copy of the IDS model, generates 8 candidate perturbations per iteration, scores them with the model, sends the best-scoring candidate to IDS to measure real evasion success |

### Adversarial Retraining
`training/retrain.py`:
1. Loads `data/data2.csv` (the live log)
2. Identifies stealth samples (`detected=0` AND `fuzz > 2`)
3. Relabels them as anomalies
4. Merges with original training data and retrains
5. Prints a **v1 vs v2 comparison table** showing improvement in detection rate

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| ML Model | scikit-learn — Isolation Forest |
| IDS Server | Flask (threaded) |
| Dashboard Backend | Flask (threaded, read-only CSV) |
| Dashboard Frontend | Vanilla JS + Chart.js (local) |
| Live Updates | Fetch API polling every 1s |
| Simulator | Flask + threading |
| Visualization | matplotlib |
| IoT Firmware | Arduino C++ (ESP32) |

---

## Notes
- This project is for **educational and research purposes**
- The attack simulation should only be used in controlled, local environments
- The `ids_model.pkl` was trained with scikit-learn 1.7.2 — if you see a version warning on 1.8+, retrain the model with `python training/train_model.py`
