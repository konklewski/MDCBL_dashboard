import os
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree

print("=== 1. BUILDING LSOA TO FORCE AND COORDINATE MAPS ===")
# Build LSOA to reported_by force mapping from street data
lsoa_force_map = {}
coords_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    df = pd.read_parquet(pf, columns=["lsoa_code", "reported_by", "latitude", "longitude"])
    temp_map = df.groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
    lsoa_force_map.update(temp_map.to_dict())
    
    # Track LSOA coordinates
    coords_list.append(df[["lsoa_code", "latitude", "longitude"]].dropna())

df_coords_all = pd.concat(coords_list).groupby("lsoa_code")[["latitude", "longitude"]].mean().reset_index()
print(f"Loaded {len(df_coords_all)} LSOA coordinates.")

print("\n=== 2. MAPPING STOP & SEARCH RECORDS SPATIALLY ===")
# Load Stop & Search data
ss_path = "data/stop_and_search_from_2021.parquet"
df_ss = pd.read_parquet(ss_path, columns=["latitude", "longitude", "outcome", "outcome_linked_to_object_of_search"]).dropna(subset=["latitude", "longitude"])
print(f"Loaded {len(df_ss)} valid Stop & Search records.")

# Build cKDTree for LSOAs
tree = cKDTree(df_coords_all[["latitude", "longitude"]].values)
ss_coords = df_ss[["latitude", "longitude"]].values

# Query nearest LSOAs
print("Querying nearest LSOAs for all Stop & Searches...")
distances, indices = tree.query(ss_coords)
df_ss["lsoa_code"] = df_coords_all.iloc[indices]["lsoa_code"].values

print("\n=== 3. MAPPING SEARCHES TO POLICE FORCES ===")
def map_street_force_to_excel(street_force):
    mapping = {
        "Avon and Somerset Constabulary": "Avon & Somerset",
        "Bedfordshire Police": "Bedfordshire",
        "Cambridgeshire Constabulary": "Cambridgeshire",
        "Cheshire Constabulary": "Cheshire",
        "Cleveland Police": "Cleveland",
        "Cumbria Constabulary": "Cumbria",
        "Derbyshire Constabulary": "Derbyshire",
        "Devon & Cornwall Police": "Devon & Cornwall",
        "Dorset Police": "Dorset",
        "Durham Constabulary": "Durham",
        "Essex Police": "Essex",
        "Gloucestershire Constabulary": "Gloucestershire",
        "Greater Manchester Police": "Greater Manchester",
        "Hampshire Constabulary": "Hampshire & Isle of Wight",
        "Hertfordshire Constabulary": "Hertfordshire",
        "Humberside Police": "Humberside",
        "Kent Police": "Kent",
        "Lancashire Constabulary": "Lancashire",
        "Leicestershire Police": "Leicestershire",
        "Lincolnshire Police": "Lincolnshire",
        "Metropolitan Police Service": "London forces: Metropolitan Police + City of London Police",
        "City of London Police": "London forces: Metropolitan Police + City of London Police",
        "Merseyside Police": "Merseyside",
        "Norfolk Constabulary": "Norfolk",
        "North Yorkshire Police": "North Yorkshire",
        "Northamptonshire Police": "Northamptonshire",
        "Northumbria Police": "Northumbria",
        "Nottinghamshire Police": "Nottinghamshire",
        "South Yorkshire Police": "South Yorkshire",
        "Staffordshire Police": "Staffordshire",
        "Suffolk Constabulary": "Suffolk",
        "Surrey Police": "Surrey",
        "Sussex Police": "Sussex",
        "Thames Valley Police": "Thames Valley",
        "Warwickshire Police": "Warwickshire",
        "West Mercia Police": "West Mercia",
        "West Midlands Police": "West Midlands",
        "West Yorkshire Police": "West Yorkshire",
        "Wiltshire Police": "Wiltshire"
    }
    return mapping.get(street_force, None)

df_ss["street_force"] = df_ss["lsoa_code"].map(lsoa_force_map)
df_ss["police_force"] = df_ss["street_force"].map(map_street_force_to_excel)

df_ss_clean = df_ss.dropna(subset=["police_force"])
print(f"Clean Stop & Search records aligned: {len(df_ss_clean)}")

print("\n=== 4. CALCULATING LOCALIZED HIT RATES ===")
def is_success(row):
    outcome = str(row["outcome"]).lower()
    if "arrest" in outcome:
        return True
    if row["outcome_linked_to_object_of_search"] == True:
        return True
    return False

df_ss_clean["success"] = df_ss_clean.apply(is_success, axis=1)

# Group and calculate success rate
df_success = df_ss_clean.groupby("police_force")["success"].agg(["sum", "count"]).reset_index()
df_success["hit_rate"] = df_success["sum"] / df_success["count"]
print(df_success.sort_values(by="hit_rate", ascending=False).head(15))

# Calculate national average hit rate
national_avg_hit_rate = df_ss_clean["success"].mean()
print(f"\nNational Average Hit Rate Benchmark: {national_avg_hit_rate:.4f} ({national_avg_hit_rate*100:.2f}%)")
