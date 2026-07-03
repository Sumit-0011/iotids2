"""
Evidence plots for the adversarial evasion benchmark.
=====================================================
Reads the artifacts produced by attacker/run_attacks.py and renders a two-panel
figure that visually proves the bypass:

  (left)  Evasion rate per attack strategy -- how much traffic slipped past.
  (right) Evasive samples plotted over the normal training cloud in
          temperature/sound space -- showing the white-box samples were pulled
          right up against "normal" (which is exactly why they evade).

Output: plots/attack_evasion.png
Run after: python attacker/run_attacks.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    report_path = os.path.join(BASE_DIR, "data", "attack_report.csv")
    evasive_path = os.path.join(BASE_DIR, "data", "evasive_samples.csv")

    if not os.path.exists(report_path):
        print("[-] No attack_report.csv found. Run: python attacker/run_attacks.py")
        return

    report = pd.read_csv(report_path)

    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Adversarial Attacks vs. Current IoT IDS (Isolation Forest + One-Class SVM)",
                 fontsize=15, fontweight="bold")

    # ── Panel 1: evasion rate per strategy ──────────────────────────────────
    colors = ["#00ff88", "#ffb703", "#ff2e63"]   # green -> amber -> red by danger
    order = report.sort_values("evasion_rate_%")
    bars = ax1.bar(order["attack"], order["evasion_rate_%"],
                   color=colors[:len(order)], edgecolor="white", linewidth=0.8)
    ax1.set_title("Evasion Rate by Attack Strategy", fontsize=12)
    ax1.set_ylabel("% of attack packets undetected")
    ax1.set_ylim(0, 105)
    ax1.tick_params(axis="x", rotation=15)
    for b, v in zip(bars, order["evasion_rate_%"]):
        ax1.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.1f}%",
                 ha="center", va="bottom", fontweight="bold")

    # ── Panel 2: evasive samples vs normal cloud ────────────────────────────
    # Normal training cloud for context.
    if os.path.exists(FINAL_DATASET):
        norm = pd.read_csv(FINAL_DATASET)
        norm = norm[norm["detected"] == 0]
        ax2.scatter(norm["temperature"], norm["sound_level"],
                    s=8, c="#3a86ff", alpha=0.25, label="normal (training)")

    if os.path.exists(evasive_path) and os.path.getsize(evasive_path) > 0:
        ev = pd.read_csv(evasive_path)
        palette = {"adaptive_fuzzing": "#ffb703", "whitebox_adversarial": "#ff2e63",
                   "baseline_aggressive": "#00ff88"}
        for atk, grp in ev.groupby("attack"):
            ax2.scatter(grp["temperature"], grp["sound_level"], s=28,
                        c=palette.get(atk, "#ffffff"), alpha=0.8,
                        edgecolor="white", linewidth=0.3,
                        label=f"evaded: {atk}")

    ax2.set_title("Evasive Samples Hiding in the Normal Cloud", fontsize=12)
    ax2.set_xlabel("temperature (C)")
    ax2.set_ylabel("sound_level (dB)")
    ax2.legend(loc="upper right", fontsize=9, framealpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    out = os.path.join(BASE_DIR, "plots", "attack_evasion.png")
    plt.savefig(out, dpi=130, facecolor=fig.get_facecolor())
    print(f"[+] Saved evasion evidence -> {out}")


if __name__ == "__main__":
    main()
