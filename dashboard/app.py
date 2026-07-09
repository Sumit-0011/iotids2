"""
IoT IDS Dashboard - Simple Flask Backend
Serves the dashboard and reads from the CSV that the IDS server writes to.
No SocketIO - the frontend polls /api/history for updates.
"""
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import pandas as pd
from flask import Flask, request, jsonify, render_template
import logging

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def stats():
    try:
        if not os.path.exists(LOG_FILE):
            return jsonify({"total_packets": 0, "anomalies_detected": 0, "stealth_rate": 0})
        df = pd.read_csv(LOG_FILE)
        total = len(df)
        anomalies = int(df['detected'].sum()) if 'detected' in df.columns else 0
        rate = round((anomalies / total * 100), 2) if total > 0 else 0
        return jsonify({"total_packets": total, "anomalies_detected": anomalies, "stealth_rate": rate})
    except pd.errors.EmptyDataError:
        return jsonify({"total_packets": 0, "anomalies_detected": 0, "stealth_rate": 0})
    except Exception as e:
        print(f"[ERROR] Stats calculation failed: {e}", file=sys.stderr)
        return jsonify({"total_packets": 0, "anomalies_detected": 0, "stealth_rate": 0})

@app.route('/api/history')
def history():
    try:
        if not os.path.exists(LOG_FILE):
            return jsonify({"total": 0, "rows": []})
        df = pd.read_csv(LOG_FILE)
        df = df.fillna(0)
        total = len(df)
        since = request.args.get('since', type=int)
        rows = df.iloc[since:] if since is not None else df.tail(100)
        return jsonify({"total": total, "rows": rows.to_dict(orient='records')})
    except pd.errors.EmptyDataError:
        return jsonify({"total": 0, "rows": []})
    except Exception as e:
        print(f"[ERROR] History retrieval failed: {e}", file=sys.stderr)
        return jsonify({"total": 0, "rows": []})

@app.route('/api/reset', methods=['POST'])
def reset():
    try:
        with open(LOG_FILE, 'w') as f:
            f.write(','.join(LOG_COLUMNS) + '\n')
    except IOError as e:
        print(f"[ERROR] Failed to reset log file: {e}", file=sys.stderr)
        return jsonify({"status": "error", "error": "Reset failed"}), 500
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print(f"[DASHBOARD] http://localhost:{DASHBOARD_PORT}")
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, threaded=True, use_reloader=False)
