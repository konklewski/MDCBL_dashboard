import pandas as pd

print("Checking maximum month in street_from_2021.parquet...")
df = pd.read_parquet("data/street_from_2021.parquet", columns=["month"])
print("Max month found:", df["month"].max())
print("Min month found:", df["month"].min())
print("Unique months:", sorted(df["month"].unique()))
