"""
Basic smoke tests for the IoT IDS project.
Run with: python -m pytest tests/ -v
Or:       python tests/test_smoke.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config import *

import csv
import tempfile
import unittest


class TestConfig(unittest.TestCase):
    def test_feature_columns_count(self):
        self.assertEqual(len(FEATURE_COLUMNS), 7,
            "FEATURE_COLUMNS should have exactly 7 entries")

    def test_feature_columns_names(self):
        expected = ["temperature", "humidity", "movement",
                    "sound_level", "battery", "fuzz", "interval"]
        self.assertEqual(FEATURE_COLUMNS, expected)

    def test_ports_are_different(self):
        self.assertNotEqual(IDS_SERVER_PORT, SIMULATOR_PORT)
        self.assertNotEqual(IDS_SERVER_PORT, DASHBOARD_PORT)
        self.assertNotEqual(SIMULATOR_PORT, DASHBOARD_PORT)

    def test_model_path_is_pkl(self):
        self.assertTrue(MODEL_PATH.endswith(".pkl"))
        self.assertTrue(SCALER_PATH.endswith(".pkl"))


class TestModelLoading(unittest.TestCase):
    def test_model_file_exists(self):
        self.assertTrue(os.path.exists(MODEL_PATH),
            f"Model not found: {MODEL_PATH}. Run training/train_model.py first.")

    def test_scaler_file_exists(self):
        self.assertTrue(os.path.exists(SCALER_PATH),
            f"Scaler not found: {SCALER_PATH}. Run training/train_model.py first.")

    def test_model_loads(self):
        import joblib, warnings
        warnings.filterwarnings("ignore")
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        self.assertIsNotNone(model)
        self.assertIsNotNone(scaler)

    def test_model_predicts(self):
        import joblib, warnings
        warnings.filterwarnings("ignore")
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        n = scaler.n_features_in_
        # Build a sample with exactly as many features as the scaler was trained on
        full_sample = [25.0, 60.0, 0, 40.0, 80.0, 0, 1000]
        sample = [full_sample[:n]]
        scaled = scaler.transform(sample)
        pred = model.predict(scaled)
        self.assertIn(pred[0], [1, -1])

    def test_model_decision_function(self):
        import joblib, warnings
        warnings.filterwarnings("ignore")
        model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        n = scaler.n_features_in_
        full_sample = [25.0, 60.0, 0, 40.0, 80.0, 0, 1000]
        sample = [full_sample[:n]]
        scaled = scaler.transform(sample)
        score = model.decision_function(scaled)[0]
        self.assertIsInstance(float(score), float)


class TestCSVLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                               delete=False, newline='')
        writer = csv.writer(self.tmp)
        writer.writerow(FEATURE_COLUMNS + ["detected"])
        writer.writerow([25.0, 60.0, 0, 40.0, 80.0, 1, 1000, 0])
        writer.writerow([30.0, 65.0, 1, 55.0, 75.0, 5, 500, 1])
        self.tmp.close()
        self.tmppath = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmppath)

    def test_csv_header(self):
        with open(self.tmppath) as f:
            reader = csv.reader(f)
            header = next(reader)
        self.assertEqual(header, FEATURE_COLUMNS + ["detected"])

    def test_csv_row_count(self):
        import pandas as pd
        df = pd.read_csv(self.tmppath)
        self.assertEqual(len(df), 2)

    def test_csv_detected_column(self):
        import pandas as pd
        df = pd.read_csv(self.tmppath)
        self.assertIn("detected", df.columns)
        self.assertTrue(set(df["detected"].unique()).issubset({0, 1}))


class TestDashboardApp(unittest.TestCase):
    def setUp(self):
        # Add parent of dashboard/ to path so 'from config import *' works inside app.py
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dashboard'))
        from app import app
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_index_returns_200(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

    def test_history_returns_dict_with_rows(self):
        import json
        r = self.client.get('/api/history')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn('rows', data, "Response should have 'rows' key")
        self.assertIn('total', data, "Response should have 'total' key")
        self.assertIsInstance(data['rows'], list)

    def test_history_since_param(self):
        import json
        r = self.client.get('/api/history?since=0')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn('rows', data)

    def test_stats_returns_dict(self):
        import json
        r = self.client.get('/api/stats')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertIn("total_packets", data)
        self.assertIn("anomalies_detected", data)
        self.assertIn("stealth_rate", data)

    def test_reset_returns_ok(self):
        import json
        r = self.client.post('/api/reset')
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.data)
        self.assertEqual(data["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
