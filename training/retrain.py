import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib


def evaluate_models(df_evasive, model_v1, scaler_v1, model_v2, scaler_v2):
    """
    Compare v1 (baseline) vs v2 (retrained) detection rates on evasive samples.
    A good retrain should catch more evasive samples in v2 than v1.
    """
    stealth = df_evasive[(df_evasive["detected"] == 0) & (df_evasive["fuzz"] > 2)]
    X_test = stealth[MODEL_FEATURES]

    pred_v1 = model_v1.predict(scaler_v1.transform(X_test))
    pred_v2 = model_v2.predict(scaler_v2.transform(X_test))

    detected_v1 = sum(1 for p in pred_v1 if p == -1)
    detected_v2 = sum(1 for p in pred_v2 if p == -1)

    total = len(X_test)
    rate_v1 = (detected_v1 / total * 100) if total > 0 else 0
    rate_v2 = (detected_v2 / total * 100) if total > 0 else 0

    print(f"\n[EVALUATION] Retrain Impact on Evasive Samples:")
    print(f"  Total evasive samples tested: {total}")
    print(f"  v1 (baseline) detection rate:  {detected_v1}/{total} ({rate_v1:.1f}%)")
    print(f"  v2 (retrained) detection rate: {detected_v2}/{total} ({rate_v2:.1f}%)")
    print(f"  Improvement: {rate_v2 - rate_v1:+.1f}%")


def retrain():
    print("[*] Loading original and evasive data...")
    df_orig = pd.read_csv(FINAL_DATASET)
    df_evasive = pd.read_csv(LOG_FILE)

    # Load the baseline v1 model for comparison
    print("[*] Loading v1 (baseline) model for evaluation...")
    model_v1 = joblib.load(MODEL_PATH)
    scaler_v1 = joblib.load(SCALER_PATH)

    # Identify stealth samples (detected == 0 but with high fuzz)
    stealth = df_evasive[(df_evasive["detected"] == 0) & (df_evasive["fuzz"] > 2)].copy()

    # Relabel them as anomalies
    stealth["detected"] = 1

    # Merge and retrain
    df_retrain = pd.concat([df_orig, stealth], ignore_index=True)

    X_train = df_retrain[df_retrain["detected"] == 0][MODEL_FEATURES]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    model = IsolationForest(**ISOLATION_FOREST_PARAMS)
    model.fit(X_scaled)

    retrain_model_path = MODEL_PATH.replace(".pkl", "_v2.pkl")
    retrain_scaler_path = SCALER_PATH.replace(".pkl", "_v2.pkl")

    joblib.dump(model, retrain_model_path)
    joblib.dump(scaler, retrain_scaler_path)

    print(f"[+] Retrained model saved to {retrain_model_path}")
    print(f"[+] Retrained scaler saved to {retrain_scaler_path}")

    # Evaluate v1 vs v2 on evasive samples
    evaluate_models(df_evasive, model_v1, scaler_v1, model, scaler)


if __name__ == "__main__":
    retrain()
