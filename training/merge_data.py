import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd

def merge():
    print("[*] Merging datasets...")
    df1 = pd.read_csv(TRAINING_DATA)
    df2 = pd.read_csv(LIVE_TRAFFIC)
    
    merged = pd.concat([df1, df2], ignore_index=True)
    merged.drop_duplicates(inplace=True)
    
    merged.to_csv(FINAL_DATASET, index=False)
    print(f"[+] Saved merged dataset to {FINAL_DATASET}")
    
if __name__ == "__main__":
    merge()
