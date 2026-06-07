import os
import pandas as pd

print("--- Reading 'Police force in England.xlsx' - Territorial Forces ---")
xlsx_path = "Police force in England.xlsx"
df_forces = pd.read_excel(xlsx_path, sheet_name="Territorial Forces")
print("Force file columns:", df_forces.columns.tolist())
# Rename columns since they wereUnnamed
df_forces.columns = ["Police_Force_Name", "Headcount_Baseline", "Officer_Allocation", "Core_Grant_2025_26"]
# Drop the first 3 rows which contain header metadata/empty rows
df_forces_clean = df_forces.iloc[3:].dropna(subset=["Police_Force_Name"])
print(df_forces_clean.head(10))
print(f"Total forces listed: {len(df_forces_clean)}")
print("Force names:")
print(df_forces_clean["Police_Force_Name"].tolist())

print("\n--- Checking crime_type and falls_within/reported_by in street_from_2021.parquet ---")
pf_path = "data/street_from_2021.parquet"
# Read a small chunk to check unique values
df_sample = pd.read_parquet(pf_path, columns=["reported_by", "falls_within", "crime_type"])
print("\nUnique crime_types in sample:")
print(df_sample["crime_type"].value_counts())

print("\nUnique reported_by forces in sample:")
print(df_sample["reported_by"].value_counts())

print("\nUnique falls_within forces in sample:")
print(df_sample["falls_within"].value_counts())
