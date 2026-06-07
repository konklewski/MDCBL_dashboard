import os
import docx
import re
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score

# Parsing crime categories
doc = docx.Document("Crime severity scores.docx")
known_categories = [
    "Anti-social behavior", "Bicycle theft", "Burglary", "Criminal damage and arson",
    "Drugs", "Other crime", "Other theft", "Possession of weapons", "Public order",
    "Robbery", "Shoplifting", "Theft from the person", "Vehicle crime", "Violence and sexual offences"
]
category_medians = {}
paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
for i, text in enumerate(paragraphs):
    matched_cat = None
    for cat in known_categories:
        if text.lower().startswith(cat.lower()):
            matched_cat = cat
            break
    if matched_cat:
        next_text = paragraphs[i+1]
        score = None
        median_match = re.search(r'median\s*[–-]\s*([\d,]+)', next_text)
        if median_match:
            score = float(median_match.group(1).replace(",", "."))
        else:
            score_match = re.search(r'score of\s*([\d,]+)', next_text)
            if score_match:
                score = float(score_match.group(1).replace(",", "."))
        if score is not None:
            category_medians[matched_cat] = score
if "Anti-social behavior" in category_medians:
    category_medians["Anti-social behaviour"] = category_medians["Anti-social behavior"]

# Map LSOAs to reported_by
lsoa_force_map = {}
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    df = pd.read_parquet(pf, columns=["lsoa_code", "reported_by"]).dropna()
    temp_map = df.groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
    lsoa_force_map.update(temp_map.to_dict())

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

# Deprivation scores
df_b = pd.read_excel("data/File_5_IoD2019_Scores.xlsx", sheet_name="IoD2019 Scores")
df_b = df_b.rename(columns={
    "LSOA code (2011)": "lsoa_code",
    "Income Score (rate)": "income_score",
    "Education, Skills and Training Score": "education_score",
    "Health Deprivation and Disability Score": "health_score",
    "Barriers to Housing and Services Score": "housing_score"
})
df_b["street_force"] = df_b["lsoa_code"].map(lsoa_force_map)
df_b["police_force"] = df_b["street_force"].map(map_street_force_to_excel)
df_b_clean = df_b.dropna(subset=["police_force"])
df_deprivation = df_b_clean.groupby("police_force")[["income_score", "education_score", "health_score", "housing_score"]].mean().reset_index()

# Extract coordinates
coords_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    df_coords = pd.read_parquet(pf, columns=["reported_by", "latitude", "longitude"]).dropna()
    coords_list.append(df_coords)
df_all_coords = pd.concat(coords_list).groupby("reported_by")[["latitude", "longitude"]].mean().reset_index()
df_all_coords["police_force"] = df_all_coords["reported_by"].map(map_street_force_to_excel)
df_all_coords = df_all_coords.dropna(subset=["police_force"])
df_force_coords = df_all_coords.groupby("police_force")[["latitude", "longitude"]].mean().reset_index()

# 2025 incident counts and CHI
df_street_2025 = pd.read_parquet("data/street_from_2021.parquet", columns=["reported_by", "month", "crime_type"])
df_street_2025 = df_street_2025[df_street_2025["month"].between("2025-01", "2025-12")].dropna()
counts = df_street_2025.groupby(["reported_by", "crime_type"]).size().reset_index(name="count")
counts["police_force"] = counts["reported_by"].map(map_street_force_to_excel)
counts = counts.dropna(subset=["police_force"])

crime_to_docx = {
    "Violence and sexual offences": "Violence and sexual offences", "Public order": "Public order",
    "Criminal damage and arson": "Criminal damage and arson", "Other theft": "Other theft",
    "Shoplifting": "Shoplifting", "Vehicle crime": "Vehicle crime", "Burglary": "Burglary",
    "Drugs": "Drugs", "Other crime": "Other crime", "Theft from the person": "Theft from the person",
    "Robbery": "Robbery", "Bicycle theft": "Bicycle theft", "Possession of weapons": "Possession of weapons",
    "Anti-social behaviour": "Anti-social behaviour"
}
counts["median_score"] = counts["crime_type"].map(crime_to_docx).map(category_medians)
counts["total_chi"] = counts["count"] * counts["median_score"]
df_chi = counts.groupby("police_force")["total_chi"].sum().reset_index()

# Merge spatial data
df_spatial = pd.merge(df_deprivation, df_chi, on="police_force")
df_spatial = pd.merge(df_spatial, df_force_coords, on="police_force")

# KNN Weights
n_forces = len(df_spatial)
W = np.zeros((n_forces, n_forces))
coords = df_spatial[["latitude", "longitude"]].values
for i in range(n_forces):
    dists = []
    for j in range(n_forces):
        if i == j:
            dists.append(np.inf)
        else:
            dist = np.sqrt(np.sum((coords[i] - coords[j])**2))
            dists.append(dist)
    nearest_neighbors = np.argsort(dists)[:3]
    W[i, nearest_neighbors] = 1.0

# Row-standardize
row_sums = W.sum(axis=1)
for i in range(n_forces):
    if row_sums[i] > 0:
        W[i, :] = W[i, :] / row_sums[i]

# Compute spatial lag
y_raw = df_spatial["total_chi"].values
spatial_lag_chi_raw = np.dot(W, y_raw)
df_spatial["spatial_lag_chi"] = spatial_lag_chi_raw

# Model evaluation on raw values
features = ["income_score", "education_score", "health_score", "housing_score", "spatial_lag_chi"]
X = df_spatial[features].values
y = df_spatial["total_chi"].values

rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
rf.fit(X, y)
y_pred = rf.predict(X)
print("Full National Fit R² (Raw):", r2_score(y, y_pred))

# Model evaluation on log values
y_log = np.log1p(df_spatial["total_chi"].values)
spatial_lag_chi_log = np.log1p(spatial_lag_chi_raw)
X_log = df_spatial[["income_score", "education_score", "health_score", "housing_score"]].copy()
X_log["spatial_lag_chi_log"] = spatial_lag_chi_log

rf_log = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
rf_log.fit(X_log.values, y_log)
y_pred_log = rf_log.predict(X_log.values)
print("Full National Fit R² (Log):", r2_score(y_log, y_pred_log))
