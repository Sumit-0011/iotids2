import os
import random
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TON_IOT_FILE = os.path.join(BASE_DIR, "ton_iot_weather.csv")
TRAINING_FILE = os.path.join(BASE_DIR, "training_data.csv")
LIVE_TRAFFIC = os.path.join(BASE_DIR, "live_traffic.csv")
FINAL_DATASET = os.path.join(BASE_DIR, "final_dataset.csv")

def generate_proxy_dataset():
    """
    Generates a realistic proxy of the TON_IoT Weather dataset.
    Real TON_IoT Weather features: ts, date, time, temperature, pressure, humidity, label, type
    """
    print("[*] Generating TON_IoT Weather proxy dataset...")
    
    # Normal data properties based on TON_IoT stats
    n_normal = 4000
    n_attack = 1000
    
    data = []
    
    # 1. Normal Traffic (label=0)
    for _ in range(n_normal):
        data.append({
            'temperature': np.random.normal(25.0, 2.0),
            'pressure': np.random.normal(1013.25, 5.0),
            'humidity': np.random.normal(60.0, 5.0),
            'label': 0,
            'type': 'normal'
        })
        
    # 2. Attack Traffic - Backdoor (label=1)
    for _ in range(n_attack // 3):
        data.append({
            'temperature': np.random.normal(35.0, 3.0),
            'pressure': np.random.normal(1000.0, 4.0),
            'humidity': np.random.normal(75.0, 4.0),
            'label': 1,
            'type': 'backdoor'
        })
        
    # 3. Attack Traffic - DDoS (label=1)
    for _ in range(n_attack // 3):
        data.append({
            'temperature': np.random.normal(45.0, 2.0),
            'pressure': np.random.normal(990.0, 2.0),
            'humidity': np.random.normal(85.0, 2.0),
            'label': 1,
            'type': 'ddos'
        })
        
    # 4. Attack Traffic - Injection (label=1)
    for _ in range(n_attack - (n_attack // 3) * 2):
        data.append({
            'temperature': np.random.normal(10.0, 5.0),
            'pressure': np.random.normal(1030.0, 5.0),
            'humidity': np.random.normal(40.0, 5.0),
            'label': 1,
            'type': 'injection'
        })
        
    df = pd.DataFrame(data)
    
    # Shuffle
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Save the raw "downloaded" dataset
    df.to_csv(TON_IOT_FILE, index=False)
    print(f"[+] Saved raw dataset to {TON_IOT_FILE}")
    
    # Preprocess for IDS
    print("[*] Preprocessing for IDS...")
    
    # The IDS needs: temperature, pressure, humidity, fuzz, interval, detected (which maps to label)
    # We will add dummy fuzz and interval since the real dataset doesn't have them, 
    # but the framework logs them. Actually, fuzz/interval are attacker controls.
    # In replay mode, fuzz=0 and interval=1000.
    df['fuzz'] = 0
    df['interval'] = 1000
    df.rename(columns={'label': 'detected'}, inplace=True)
    
    # Ensure columns are ordered
    columns = ['temperature', 'pressure', 'humidity', 'fuzz', 'interval', 'detected', 'type']
    df = df[columns]
    
    # Split: Training data (only normal data for one-class classifier)
    normal_df = df[df['detected'] == 0].copy()
    train_df = normal_df.sample(n=2000, random_state=42)
    
    # Live Traffic: The rest of normal + all attacks (used for simulation replay)
    test_df = df.drop(train_df.index)
    
    # Drop the 'type' column for training as the original IDS didn't use it
    train_df = train_df.drop(columns=['type'])
    test_df = test_df.drop(columns=['type'])
    
    train_df.to_csv(TRAINING_FILE, index=False)
    test_df.to_csv(LIVE_TRAFFIC, index=False)
    
    # Also create final_dataset.csv for the evaluation scripts
    final_df = pd.concat([train_df, test_df], ignore_index=True)
    final_df.to_csv(FINAL_DATASET, index=False)
    
    print(f"[+] Saved training dataset (2000 normal samples) to {TRAINING_FILE}")
    print(f"[+] Saved live replay dataset ({len(test_df)} mixed samples) to {LIVE_TRAFFIC}")
    print(f"[+] Saved final_dataset ({len(final_df)} samples) to {FINAL_DATASET}")

if __name__ == "__main__":
    generate_proxy_dataset()
