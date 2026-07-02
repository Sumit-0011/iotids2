"""
Basic unit tests for the IDS model and scoring logic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
import joblib
import tempfile
import csv
from config import MODEL_PATH, SCALER_PATH, MODEL_FEATURES


class TestIDSModel(unittest.TestCase):
    """Test Isolation Forest model loading and scoring."""

    def setUp(self):
        self.model = joblib.load(MODEL_PATH)
        self.scaler = joblib.load(SCALER_PATH)

    def test_model_loads(self):
        """Verify model and scaler are loaded successfully."""
        self.assertIsNotNone(self.model)
        self.assertIsNotNone(self.scaler)

    def test_scaler_dimensions(self):
        """Verify scaler expects the correct number of features."""
        self.assertEqual(self.scaler.n_features_in_, len(MODEL_FEATURES))
        self.assertEqual(self.scaler.n_features_in_, 5)

    def test_model_scores_normal_as_benign(self):
        """Normal sensor readings should score positively (not anomalous)."""
        normal = [[25.0, 60.0, 0, 40.0, 80.0]]  # Within baseline ranges
        scaled = self.scaler.transform(normal)
        score = self.model.decision_function(scaled)[0]
        prediction = self.model.predict(scaled)[0]

        self.assertGreater(score, -0.5, "Normal data should score >= -0.5")
        self.assertEqual(prediction, 1, "Normal data should predict as 1 (normal)")

    def test_model_flags_anomalous_as_anomaly(self):
        """Out-of-distribution data should score negatively (anomalous)."""
        anomaly = [[300.0, 5.0, 1, 190.0, 2.0]]  # Extreme values
        scaled = self.scaler.transform(anomaly)
        score = self.model.decision_function(scaled)[0]
        prediction = self.model.predict(scaled)[0]

        self.assertLess(score, 0, "Anomalous data should score < 0")
        self.assertEqual(prediction, -1, "Anomalous data should predict as -1 (anomaly)")

    def test_scaler_transforms_correctly(self):
        """Verify scaler standardizes data without errors."""
        samples = [
            [25.0, 60.0, 0, 40.0, 80.0],
            [26.0, 61.0, 1, 41.0, 79.0],
            [24.0, 59.0, 0, 39.0, 81.0],
        ]
        scaled = self.scaler.transform(samples)
        self.assertEqual(scaled.shape, (3, 5), "Scaled output should be (3, 5)")


class TestCSVLogging(unittest.TestCase):
    """Test CSV logging functionality."""

    def test_csv_write_and_read(self):
        """Verify CSV data can be written and read back correctly."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as f:
            temp_csv = f.name
            writer = csv.writer(f)
            # Write header: timestamp + 7 feature columns + detected + score
            header = ['timestamp', 'temperature', 'humidity', 'movement', 'sound_level', 'battery', 'fuzz', 'interval', 'detected', 'score']
            writer.writerow(header)
            # Write a sample row (all strings since CSV is text)
            row = ['12:00:00', '25.0', '60.0', '0', '40.0', '80.0', '0', '1000', '0', '0.1234']
            writer.writerow(row)

        try:
            # Read it back
            with open(temp_csv, 'r') as f:
                reader = csv.reader(f)
                read_header = next(reader)
                read_row = next(reader)

            self.assertEqual(read_header, header)
            self.assertEqual(read_row, row)
        finally:
            os.unlink(temp_csv)

    def test_csv_column_count(self):
        """Verify CSV has the correct column count: timestamp + 5 sensors + 2 meta + 2 results."""
        # timestamp (1) + MODEL_FEATURES (5) + META (2) + detected/score (2) = 10
        from config import FEATURE_COLUMNS
        header = ['timestamp'] + FEATURE_COLUMNS + ['detected', 'score']
        self.assertEqual(len(header), 10)


if __name__ == '__main__':
    unittest.main()
