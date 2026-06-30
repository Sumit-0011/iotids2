import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

data = pd.read_csv("data2.csv")
samples = list(range(len(data)))

# Key boundaries
normal_end = 74      # rows 0-74: attack happening but NOT detected
attack_start = 75    # rows 75-82: finally detected

fig, axes = plt.subplots(4, 1, figsize=(14, 12))
fig.patch.set_facecolor('#0f0f0f')
fig.suptitle("Adaptive Fuzzing Attack — Bypassing the IDS Model",
             fontsize=15, fontweight='bold', color='white', y=0.99)

def shade(ax):
    # Phase 1: Stealth zone (0 to 74) — attacking but undetected
    ax.axvspan(0, normal_end, alpha=0.12, color='#00FF88', zorder=0)
    # Phase 2: Detected zone (75-82)
    ax.axvspan(normal_end, 82, alpha=0.25, color='#FF3333', zorder=0)
    ax.axvline(x=normal_end, color='red', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.set_facecolor('#1a1a2e')
    ax.tick_params(colors='white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#444')
    ax.grid(True, alpha=0.2, color='#555')

# ── Panel 1: Detection ──────────────────────────────
ax = axes[0]
# Color each dot: green=0, red=1
for i, (s, d) in enumerate(zip(samples, data['detected'])):
    color = '#FF3333' if d == 1 else '#00BFFF'
    ax.scatter(s, d, color=color, s=25, zorder=5)
ax.plot(samples, data['detected'], color='#00BFFF', linewidth=1, alpha=0.5, zorder=4)
shade(ax)
ax.set_ylabel("0=Safe  1=Attack", fontsize=9, color='white')
ax.set_yticks([0, 1])
ax.set_title("① DETECTION — Blue dots = model said SAFE (missed attack), Red dots = CAUGHT", fontsize=9, pad=5)
ax.set_ylim(-0.3, 1.5)

# Annotations
ax.annotate('75 samples\nUNDETECTED\n(Attack happening!)',
            xy=(37, 0), xytext=(37, 0.7),
            color='#00FF88', fontsize=8, ha='center',
            arrowprops=dict(arrowstyle='->', color='#00FF88'))
ax.annotate('FINALLY\nDETECTED\n(Too late!)',
            xy=(78, 1), xytext=(78, 1.3),
            color='#FF3333', fontsize=8, ha='center')

# ── Panel 2: Temperature ────────────────────────────
ax = axes[1]
baseline = data['temperature'][:10].mean()
ax.plot(samples, data['temperature'], color='#FF6B35', linewidth=2, label='Temperature', zorder=5)
ax.axhline(y=baseline, color='#888', linestyle=':', linewidth=1.5, label=f'Normal baseline (~{baseline:.0f}°C)')
shade(ax)
ax.set_ylabel("Temperature (°C)", fontsize=9, color='white')
ax.set_title("② TEMPERATURE DRIFT — Attacker slowly increased from ~25°C → 64°C to find detection boundary", fontsize=9, pad=5)
ax.legend(fontsize=8, facecolor='#222', labelcolor='white', framealpha=0.8)

# Arrow showing drift
ax.annotate('', xy=(74, 31), xytext=(10, 25),
            arrowprops=dict(arrowstyle='->', color='yellow', lw=2))
ax.text(35, 22, 'Gradual drift upward →', color='yellow', fontsize=8)

# ── Panel 3: Humidity ───────────────────────────────
ax = axes[2]
base_h = data['humidity'][:10].mean()
ax.plot(samples, data['humidity'], color='#7EC8E3', linewidth=2, label='Humidity', zorder=5)
ax.axhline(y=base_h, color='#888', linestyle=':', linewidth=1.5, label=f'Normal baseline (~{base_h:.0f}%)')
shade(ax)
ax.set_ylabel("Humidity (%)", fontsize=9, color='white')
ax.set_title("③ HUMIDITY DRIFT — Also manipulated alongside temperature (both changed together to avoid single-sensor detection)", fontsize=9, pad=5)
ax.legend(fontsize=8, facecolor='#222', labelcolor='white', framealpha=0.8)

# ── Panel 4: Sound Level ────────────────────────────
ax = axes[3]
base_s = data['sound_level'][:10].mean()
ax.plot(samples, data['sound_level'], color='#C77DFF', linewidth=2, label='Sound Level', zorder=5)
ax.axhline(y=base_s, color='#888', linestyle=':', linewidth=1.5, label=f'Normal baseline (~{base_s:.0f})')
shade(ax)
ax.set_ylabel("Sound Level", fontsize=9, color='white')
ax.set_xlabel("Sample Number (each = 1 second)", fontsize=10, color='white')
ax.set_title("④ SOUND LEVEL — Third sensor manipulated, all 3 sensors drifted gradually together", fontsize=9, pad=5)
ax.legend(fontsize=8, facecolor='#222', labelcolor='white', framealpha=0.8)

# ── Bottom legend ────────────────────────────────────
p1 = mpatches.Patch(color='#00FF88', alpha=0.5, label='STEALTH PHASE — 75 samples, attack undetected')
p2 = mpatches.Patch(color='#FF3333', alpha=0.5, label='DETECTED PHASE — Model finally caught it (too late, data already stolen)')
fig.legend(handles=[p1, p2], loc='lower center', ncol=2,
           fontsize=9, facecolor='#222', labelcolor='white',
           framealpha=0.9, bbox_to_anchor=(0.5, 0.005))

plt.tight_layout(rect=[0, 0.055, 1, 0.98])
plt.savefig("final_graph.png", dpi=150, bbox_inches='tight', facecolor='#0f0f0f')
print("Saved final_graph.png")
plt.show()