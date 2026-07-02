"""
Generate a clean baseline training dataset with purely normal (fuzz=0) sensor readings,
then retrain the Isolation Forest model on it.

Run this once to fix the model:
    python training/generate_baseline_and_retrain.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
import numpy as np
import joblib
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

np.random.seed(42)

# ── 1. Generate purely normal baseline data ───────────────────
print("[1] Generating clean normal baseline data...")
n_samples = 2000

# Realistic IoT sensor normal operating ranges
temperature = np.random.normal(loc=25.0, scale=0.8, size=n_samples)   # 25°C ± 0.8
humidity    = np.random.normal(loc=60.0, scale=1.5, size=n_samples)   # 60% ± 1.5
movement    = np.random.choice([0, 1], size=n_samples, p=[0.7, 0.3])  # 70% no motion
sound_level = np.random.normal(loc=40.0, scale=1.0, size=n_samples)   # 40 dB ± 1.0
battery     = np.clip(np.linspace(82, 78, n_samples) +
              np.random.normal(0, 0.1, n_samples), 70, 100)            # slowly draining

df_normal = pd.DataFrame({
    "temperature": np.round(temperature, 2),
    "humidity":    np.round(humidity, 2),
    "movement":    movement,
    "sound_level": np.round(sound_level, 2),
    "battery":     np.round(battery, 2),
    "fuzz":        0,
    "interval":    1000,
    "detected":    0,
})

# ── 2. Add a small number of obvious attacks so Isolation Forest
#       can calibrate what "anomalous" means (contamination fraction)
print("[2] Adding synthetic attack samples for contamination calibration...")
n_attack = 200

atk_temp    = np.random.choice([-10, 60, 80, 100], size=n_attack)
atk_hum     = np.random.choice([0, 5, 95, 100, 120], size=n_attack)
atk_sound   = np.random.uniform(150, 220, n_attack)
atk_battery = np.random.uniform(-5, 10, n_attack)
atk_fuzz    = np.random.randint(8, 15, n_attack)

df_attack = pd.DataFrame({
    "temperature": np.round(atk_temp, 2),
    "humidity":    np.round(atk_hum, 2),
    "movement":    1,
    "sound_level": np.round(atk_sound, 2),
    "battery":     np.round(atk_battery, 2),
    "fuzz":        atk_fuzz,
    "interval":    200,
    "detected":    1,
})

df_full = pd.concat([df_normal, df_attack], ignore_index=True)
df_full.to_csv(FINAL_DATASET, index=False)
print(f"    Saved {len(df_full)} rows to {os.path.basename(FINAL_DATASET)}")
print(f"    Normal: {len(df_normal)} | Attack: {len(df_attack)}")

# ── 3. Train Isolation Forest on NORMAL DATA ONLY ─────────────
print("[3] Training Isolation Forest on normal data only...")
X_train = df_normal[MODEL_FEATURES]

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# contamination = expected fraction of anomalies AT INFERENCE time (not in training set)
params = dict(ISOLATION_FOREST_PARAMS)
params["contamination"] = 0.05   # expect ~5% anomaly rate in live traffic
model = IsolationForest(**params)
model.fit(X_scaled)

os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
joblib.dump(model, MODEL_PATH)
joblib.dump(scaler, SCALER_PATH)
print(f"    Model saved -> {os.path.basename(MODEL_PATH)}")
print(f"    Scaler saved -> {os.path.basename(SCALER_PATH)}")

# ── 4. Quick sanity-check ─────────────────────────────────────
print("\n[4] Sanity check:")

def check(label, sample):
    sc = scaler.transform([sample])
    pred = model.predict(sc)[0]
    score = model.decision_function(sc)[0]
    verdict = "NORMAL" if pred == 1 else "ANOMALY"
    print(f"    {label:<30} score={score:+.4f}  -> {verdict}")

check("Normal baseline (25C, 60%RH)", [25.0, 60.0, 0, 40.0, 80.0])
check("Slight drift   (28C, 63%RH)", [28.0, 63.0, 0, 42.0, 79.0])
check("Stealth attack (32C, 66%RH)", [32.0, 66.0, 1, 45.0, 78.0])
check("Aggressive     (45C, 80%RH)", [45.0, 80.0, 1, 70.0, 70.0])
check("Extreme attack (80C, 5%RH)",  [80.0,  5.0, 1, 180.0, 5.0])

print("\n[DONE] Retrain complete. Restart the system to use the new model.")
print("       python run.py --smart-attack")
