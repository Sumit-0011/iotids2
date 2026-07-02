import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

def train():
    print("[*] Loading dataset...")
    df = pd.read_csv(FINAL_DATASET)
    
    # Train only on normal data, using genuine sensor features (not attack knobs)
    df_normal = df[df["detected"] == 0]
    X_train = df_normal[MODEL_FEATURES]
    
    print("[*] Scaling features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)
    
    print("[*] Training Isolation Forest...")
    model = IsolationForest(**ISOLATION_FOREST_PARAMS)
    model.fit(X_scaled)
    
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    print(f"[+] Model saved to {MODEL_PATH}")
    print(f"[+] Scaler saved to {SCALER_PATH}")

    # Also fit the second ensemble detector (One-Class SVM) in the same space,
    # so a from-scratch train yields a ready-to-use dual-detector ensemble.
    from sklearn.svm import OneClassSVM
    print("[*] Training One-Class SVM (ensemble detector)...")
    ocsvm = OneClassSVM(**OCSVM_PARAMS)
    ocsvm.fit(X_scaled)
    joblib.dump(ocsvm, OCSVM_MODEL_PATH)
    print(f"[+] One-Class SVM saved to {OCSVM_MODEL_PATH}")

if __name__ == "__main__":
    train()
