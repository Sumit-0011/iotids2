"""
Train the second detector for the ensemble: a One-Class SVM.

Design choice: the One-Class SVM is fit in the SAME feature space as the existing
Isolation Forest - it reuses the already-trained StandardScaler (scaler.pkl) and
is trained on the same normal-only data. This means:
  * The Isolation Forest model + scaler are NOT touched or retrained.
  * At inference both detectors see identical scaled inputs, so their verdicts
    are directly comparable.

Run this once after train_model.py (or via run.py --train-ensemble) to produce
models/ocsvm_model.pkl. The IDS server loads it automatically if present and
falls back to Isolation-Forest-only if it is missing.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
from sklearn.svm import OneClassSVM
import joblib


def train_ensemble():
    if not os.path.exists(SCALER_PATH):
        print(f"[-] Scaler not found at {SCALER_PATH}. Run training/train_model.py first.")
        return

    print("[*] Loading dataset...")
    df = pd.read_csv(FINAL_DATASET)

    # Train only on normal data, using the same genuine sensor features.
    df_normal = df[df["detected"] == 0]
    X_train = df_normal[MODEL_FEATURES]

    print("[*] Reusing existing scaler (Isolation Forest space)...")
    scaler = joblib.load(SCALER_PATH)
    X_scaled = scaler.transform(X_train)

    print("[*] Training One-Class SVM (second detector)...")
    ocsvm = OneClassSVM(**OCSVM_PARAMS)
    ocsvm.fit(X_scaled)

    os.makedirs(os.path.dirname(OCSVM_MODEL_PATH), exist_ok=True)
    joblib.dump(ocsvm, OCSVM_MODEL_PATH)
    print(f"[+] One-Class SVM saved to {OCSVM_MODEL_PATH}")

    # Quick sanity report: how the two detectors agree on the training normals.
    iforest = joblib.load(MODEL_PATH)
    if_pred = iforest.predict(X_scaled)
    svm_pred = ocsvm.predict(X_scaled)
    if_flag = (if_pred == -1).mean() * 100
    svm_flag = (svm_pred == -1).mean() * 100
    print(f"[i] False-positive rate on normal training data: "
          f"IsolationForest={if_flag:.1f}%, OneClassSVM={svm_flag:.1f}%")


if __name__ == "__main__":
    train_ensemble()
