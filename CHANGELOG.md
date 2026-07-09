# CHANGELOG — IoT Intrusion Detection System

All notable changes to this project are documented in this file.
Entries are ordered **newest first**. Each version records the date/time
(IST, UTC+5:30), a summary, and per-file change details.

---

## [v3.0] — 2026-07-09 23:15 IST

### Blue-Team Supervised Adversarial Detector Integration

Completes the `blue-team-detector` branch by wiring the trained
`models/detector.pkl` (RandomForest hardened against white-box evasion)
into the live IDS server as a third vote in the detection ensemble,
surfacing its verdict in the dashboard, adding an evaluation script, and
maintaining this changelog.

### Changed

#### `server/ids_ml.py`
- Updated module docstring to describe the new triple-detector architecture.
- Added `import pandas as pd` at module level (needed for RF inference).
- Load `models/detector.pkl` at startup; degrade gracefully if absent.
- Added **Detector 3** inference block: feeds raw (unscaled) sensor vector
  to the RandomForest; RF labels `1 = attack`, `0 = normal`.
- Ensemble `OR` vote now covers all three detectors: IF, OCSVM, and RF.
- CSV row writer now emits the `detector` column (fixes 14-col → 15-col
  schema mismatch introduced when `LOG_COLUMNS` was updated in `config.py`).
- JSON response now includes `"detector"` field for the dashboard.

#### `dashboard/templates/index.html`
- Updated intel panel subtitle: "Dual-Detector Ensemble" → "Triple-Detector Ensemble".
- Added third model chip (`chipDetector` / `verdictDetector`) for Adversarial RF.
- Updated footer version string: v2.0 → v3.0 with new component list.

#### `dashboard/static/dashboard.js`
- `updateIntel()` now reads `point.detector`; falls back to `0` for old CSV rows.
- Calls `setChip('chipDetector', 'verdictDetector', detv)` for the new chip.
- Ensemble verdict message rebuilt to name all detectors that fired
  (e.g., "⚠ ATTACK — Isolation Forest + Adversarial RF flagged it").
- Safe message updated: "both detectors clear" → "all detectors clear".

### Added

#### `training/eval_detector.py` *(new)*
- Evaluation script: compares v1 (IF only), v2 (IF+OCSVM), and v3 (IF+OCSVM+RF)
  side-by-side against three attack strategies:
  `baseline_aggressive`, `adaptive_fuzzing`, `whitebox_adversarial`.
- Prints a formatted comparison table with detection rates and v2→v3 gain (pp).
- Saves `data/eval_report.csv` for downstream plotting.
- Run with: `python training/eval_detector.py [-n <samples>]`

#### `CHANGELOG.md` *(this file)*
- New file at project root documenting all project changes with dates and times.

---

## [v2.1] — 2026-07-03 16:00 IST

### Red-Team Attack Suite

*(Committed on branch `blue-team-detector`, authored with Claude Opus 4.8)*

Added a reproducible adversarial evasion benchmark and white-box attack
that achieves 100% evasion against the v2 dual-detector ensemble.

### Added

#### `attacker/adversarial_whitebox.py` *(new)*
- White-box minimal-perturbation boundary attack against the IF+OCSVM ensemble.
- Walks a malicious seed toward the normal centroid until the ensemble stops flagging it.
- Can POST crafted packets to the live IDS server for real evasion measurement.

#### `attacker/run_attacks.py` *(new)*
- Reproducible offline evasion benchmark for three attack strategies.
- Outputs `data/attack_report.csv` and `data/evasive_samples.csv` (269 samples).

#### `plots/attack_plots.py` *(new)*
- Visualisation script for evasion evidence plots.

#### `data/evasive_samples.csv` *(generated)*
- 269 undetected adversarial attack samples; used as seed corpus for v3 detector training.

### Changed

#### `run.py`
- Added `--adversarial` flag: launches live white-box bypass demo
  (IDS + dashboard + adversarial attacker, simulator disabled).

---

## [v2.0] — 2026-07-02 18:23 IST

### Real-Time Dashboard & Dual-Detector Ensemble

*(Committed by sumit)*

Major upgrade adding a live web dashboard and a second unsupervised detector.

### Added

#### `dashboard/` *(new directory)*
- `app.py` — Flask backend serving the dashboard; exposes `/api/history`,
  `/api/stats`, and `/api/reset` endpoints; reads `data/data2.csv`.
- `templates/index.html` — Cybersecurity dark-theme dashboard with 4 real-time
  Chart.js sensor charts, stats row, Detection Intelligence panel (ensemble +
  XAI attribution bars), and detection log table.
- `static/style.css` — Full dark theme with glassmorphism cards, glow effects,
  animated grid background, and micro-animations.
- `static/dashboard.js` — 1-second polling client with sliding 60-point charts,
  `since=N` cursor for incremental updates, and ensemble chip rendering.
- `static/chart.min.js` — Chart.js bundled locally (no CDN dependency).

#### `training/train_ensemble.py` *(new)*
- Trains One-Class SVM reusing the existing StandardScaler from `scaler.pkl`.
- Outputs `models/ocsvm_model.pkl`.

#### `models/ocsvm_model.pkl` *(generated)*
- One-Class SVM model for the second detector.

### Changed

#### `server/ids_ml.py`
- Added One-Class SVM second detector (optional, graceful fallback).
- Added XAI explainability: z-score based feature attribution.
- Extended CSV log schema with `iforest`, `ocsvm`, `top_feature`, `attribution` columns.
- JSON response now includes per-detector verdicts and attribution string.

#### `config.py`
- Added `OCSVM_MODEL_PATH`, `OCSVM_PARAMS`, `ENSEMBLE_RULE`.
- Extended `LOG_COLUMNS` with ensemble and XAI fields.

#### `training/train_model.py`
- Now also trains and saves the One-Class SVM as part of from-scratch training.

---

## [v1.0] — 2026-06-30 15:15 IST

### Initial Commit

*(Committed by gojosaturo25 — Vishal Kumar)*

First working version of the IoT Intrusion Detection System.

### Added

#### Core Components
- `server/ids_ml.py` — Flask IDS server with Isolation Forest anomaly detector.
- `server/ids_rule.py` — Rule-based IDS (threshold-based, for comparison).
- `simulator/esp32_simulator.py` — Python ESP32 simulator cycling through
  Normal → Stealth Attack → Aggressive Attack → Reset phases.
- `attacker/adaptive_fuzzer.py` — Real-time feedback-driven fuzzer.
- `attacker/smart_controller.py` — ML-guided evasion controller (local model scoring).

#### Training Pipeline
- `training/train_model.py` — Trains Isolation Forest on 2,000 synthetic normal samples.
- `training/merge_data.py` — Merges multiple training datasets.
- `training/retrain.py` — Adversarial retraining pipeline (v1 vs v2 comparison).
- `training/generate_baseline_and_retrain.py` — Generates clean baseline training data.

#### Models & Data
- `models/ids_model.pkl` — Trained Isolation Forest (100 estimators, contamination=0.1).
- `models/scaler.pkl` — StandardScaler fitted on 5 sensor features.
- `data/training_data.csv` — Bootstrap normal training data.
- `data/final_dataset.csv` — Merged training dataset used for model training.

#### Utilities
- `config.py` — Central configuration: ports, paths, feature lists, hyperparameters.
- `run.py` — Unified launcher supporting `--attack`, `--smart-attack`,
  `--retrain`, `--plot`, `--rule-based`, `--no-dashboard` flags.
- `plots/plot_graph.py` — matplotlib 4-panel analysis graph from `data2.csv`.
- `firmware/esp32code.txt` — Reference Arduino sketch for real ESP32 hardware.

#### Tests
- `tests/test_smoke.py` — 14 smoke tests covering config, model loading, CSV I/O,
  and dashboard API endpoints.
- `tests/test_ids_model.py` — 10 unit tests for Isolation Forest model behaviour.
- `check_detections.py` — Quick CLI utility to count detections in `data2.csv`.

#### Documentation
- `README.md` — Quick-start guide, architecture diagram, launcher options, demo script.
- `PROJECT_DOCUMENTATION.md` — Full academic writeup covering problem statement,
  architecture, ML deep-dive, results, conclusions, and future work.
- `.gitignore` — Standard Python gitignore.

---

*Maintained by the IoT IDS project team. Local time zone: IST (UTC+5:30).*
