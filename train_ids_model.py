import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import joblib

# 🔹 Load dataset
data = pd.read_csv("final_dataset.csv")


normal_data = data[data["detected"] == 0]

# 🔹 Select features
feature_columns = [
    "temperature",
    "humidity",
    "movement",
    "sound_level",
    "battery",
    "fuzz",
    "interval"
]

X = normal_data[feature_columns]

# 🔹 Normalize
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)


model = IsolationForest(
    n_estimators=100,
    contamination=0.1,
    random_state=42
)

model.fit(X_scaled)

# 🔹 Save model + scaler
joblib.dump(model, "ids_model.pkl")
joblib.dump(scaler, "scaler.pkl")

print("Isolation Forest IDS model trained successfully!")
