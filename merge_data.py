import pandas as pd

# Load both datasets
df1 = pd.read_csv("training_data.csv")
df2 = pd.read_csv("live_traffic.csv")

# Combine
df = pd.concat([df1, df2], ignore_index=True)

# Optional: remove duplicates
df = df.drop_duplicates()

# Save final dataset
df.to_csv("final_dataset.csv", index=False)

print("Datasets merged successfully!")
print("Total rows:", len(df))
