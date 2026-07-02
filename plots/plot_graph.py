import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
import matplotlib.pyplot as plt

def plot():
    print("[*] Generating visualization...")
    df = pd.read_csv(LOG_FILE)
    
    if len(df) == 0:
        print("[-] No data to plot.")
        return
        
    plt.style.use('dark_background')
    fig, axes = plt.subplots(4, 1, figsize=(12, 16), sharex=True)
    
    axes[0].plot(df['temperature'], color='#ff6b35')
    axes[0].set_title("Temperature")
    
    axes[1].plot(df['humidity'], color='#7ec8e3')
    axes[1].set_title("Humidity")
    
    axes[2].plot(df['sound_level'], color='#c77dff')
    axes[2].set_title("Sound Level")
    
    axes[3].plot(df['battery'], color='#00ff88')
    axes[3].set_title("Battery")
    
    # Shade attack regions based on 'fuzz' or 'detected'
    for ax in axes:
        transitions = df.index[df['detected'].diff() == 1].tolist()
        if transitions:
            attack_start = transitions[0]
            ax.axvspan(attack_start, len(df), color='red', alpha=0.2)
            
    plt.tight_layout()
    plot_path = os.path.join(BASE_DIR, "plots", "final_graph.png")
    plt.savefig(plot_path)
    print(f"[+] Plot saved to {plot_path}")

if __name__ == "__main__":
    plot()
