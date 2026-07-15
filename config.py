"""
Central configuration for the IoT IDS project.
All ports, paths, and URLs are defined here - no hardcoded values in other files.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Network Configuration
IDS_SERVER_HOST = "0.0.0.0"
IDS_SERVER_PORT = 8080
SIMULATOR_HOST = "0.0.0.0"
SIMULATOR_PORT = 8081
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# URLs (used by attacker/simulator to connect)
IDS_SERVER_URL = f"http://localhost:{IDS_SERVER_PORT}"
SIMULATOR_CMD_URL = f"http://localhost:{SIMULATOR_PORT}/command"
FEEDBACK_URL = f"http://localhost:{IDS_SERVER_PORT}/feedback"
DASHBOARD_URL = f"http://localhost:{DASHBOARD_PORT}"

# File Paths
MODEL_PATH = os.path.join(BASE_DIR, "models", "ids_model.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "models", "scaler.pkl")
LOG_FILE = os.path.join(BASE_DIR, "data", "data2.csv")
TRAINING_DATA = os.path.join(BASE_DIR, "data", "training_data.csv")
FINAL_DATASET = os.path.join(BASE_DIR, "data", "final_dataset.csv")
LIVE_TRAFFIC = os.path.join(BASE_DIR, "data", "live_traffic.csv")

# Feature Columns
#
# MODEL_FEATURES are the genuine sensor readings the IDS model is trained and
# scored on. `fuzz` and `interval` are the ATTACKER's control knobs, not sensor
# data - a real IDS never sees them, and training on them makes detection
# circular (high fuzz trivially correlates with "anomaly"). They are kept in
# META_COLUMNS so they are still logged for analysis, but never fed to the model.
MODEL_FEATURES = [
    "temperature",
    "pressure",
    "humidity",
]

# Attack-control metadata: logged alongside each sample but excluded from the model.
META_COLUMNS = [
    "fuzz",
    "interval",
]

# Full set of numeric columns stored in datasets and CSV logs (schema order).
FEATURE_COLUMNS = MODEL_FEATURES + META_COLUMNS

# Model Hyperparameters
ISOLATION_FOREST_PARAMS = {
    "n_estimators": 100,
    "contamination": 0.1,
    "random_state": 42
}

# ─────────────────────────────────────────────────────────────────────────────
# Ensemble Detection (dual-detector defense)
#
# The IDS runs TWO independent one-class detectors from different model families:
#   1. Isolation Forest  - tree-based, isolates anomalies by random splits
#   2. One-Class SVM      - kernel boundary around the normal region
# They fail differently, so an attacker who learns to slip past one still has to
# evade the other. The ensemble verdict flags a packet if EITHER model flags it
# ("or" voting) - biased toward catching stealth attacks. Both are fit on the
# SAME StandardScaler space, so the Isolation Forest path is completely unchanged.
# ─────────────────────────────────────────────────────────────────────────────
OCSVM_MODEL_PATH = os.path.join(BASE_DIR, "models", "ocsvm_model.pkl")

# One-Class SVM hyperparameters. `nu` ~ expected anomaly fraction (mirrors the
# Isolation Forest contamination); rbf kernel gives a non-linear normal boundary.
OCSVM_PARAMS = {
    "kernel": "rbf",
    "gamma": "scale",
    "nu": 0.1,
}

# Ensemble voting rule: "or" = flag if any model flags (max sensitivity),
# "and" = flag only if all models agree (max precision).
ENSEMBLE_RULE = "or"

# ─────────────────────────────────────────────────────────────────────────────
# Supervised Adversarial Detector (blue-team, v3)
#
# The one-class IF/OCSVM models only know "far from normal", so an adversary who
# hugs the normal boundary evades both (see attacker/adversarial_whitebox.py).
# This third detector is a SUPERVISED classifier trained on labeled normal-vs-
# attack data AND hardened with an adversarial-training loop, so it learns the
# actual attack boundary instead of just a distance-from-normal radius.
#
# It joins the server as a 3rd vote under the same ENSEMBLE_RULE. If the file is
# missing, the server degrades gracefully to the IF+OCSVM ensemble.
# Trained on RAW sensor features (tree models don't need scaling).
# ─────────────────────────────────────────────────────────────────────────────
DETECTOR_MODEL_PATH = os.path.join(BASE_DIR, "models", "detector.pkl")

# RandomForest hyperparameters for the supervised detector.
DETECTOR_PARAMS = {
    "n_estimators": 200,
    "max_depth": None,
    "class_weight": "balanced",
    "random_state": 42,
    "n_jobs": -1,
}

# Adversarial-training loop: how many attack->retrain rounds, and how many
# adversarial samples to mine against the current model each round.
ADV_TRAIN_ROUNDS = 6
ADV_SAMPLES_PER_ROUND = 300

# CSV log schema (order matters - written by server, read by dashboard).
# Extends the original schema with the ensemble + explainability columns.
# NOTE: kept separate from FEATURE_COLUMNS so existing tooling that relies on the
# 7 numeric feature columns is unaffected. Older CSV rows without these columns
# are backfilled with 0 by the dashboard (df.fillna(0)).
#   detected     - final ensemble verdict (0 safe / 1 attack)
#   score        - Isolation Forest decision_function score (negative = anomalous)
#   iforest      - Isolation Forest verdict (0/1)
#   ocsvm        - One-Class SVM verdict (0/1)
#   top_feature  - sensor that contributed most to the anomaly (XAI)
#   attribution  - "temp:78|sound:15|..." per-feature % contribution (XAI)
#   detector     - supervised adversarial detector verdict (0/1), 0 if absent
LOG_COLUMNS = (
    ["timestamp"] + FEATURE_COLUMNS
    + ["detected", "score", "iforest", "ocsvm", "detector", "top_feature", "attribution"]
)
