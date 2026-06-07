import os
import docx
import re
import pandas as pd
import numpy as np

print("=== 1. PARSING CRIME SEVERITY MEDIANS ===")
doc = docx.Document("Crime severity scores.docx")
known_categories = [
    "Anti-social behavior",
    "Bicycle theft",
    "Burglary",
    "Criminal damage and arson",
    "Drugs",
    "Other crime",
    "Other theft",
    "Possession of weapons",
    "Public order",
    "Robbery",
    "Shoplifting",
    "Theft from the person",
    "Vehicle crime",
    "Violence and sexual offences"
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
            else:
                have_score_match = re.search(r'have a score of\s*([\d,]+)', next_text)
                if have_score_match:
                    score = float(have_score_match.group(1).replace(",", "."))
        
        if score is not None:
            category_medians[matched_cat] = score

if "Anti-social behavior" in category_medians:
    category_medians["Anti-social behaviour"] = category_medians["Anti-social behavior"]

print(f"Parsed {len(category_medians)} category medians.")

print("\n=== 2. EXTRACTING LSOA TO STREET FORCE MAPPINGS ===")
lsoa_force_map = {}
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    df = pd.read_parquet(pf, columns=["lsoa_code", "reported_by"]).dropna()
    temp_map = df.groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
    lsoa_force_map.update(temp_map.to_dict())

print("\n=== 3. CONFIGURING FORCE-NAME ALIGNMENT MAP ===")
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

print("\n=== 4. LOADING DEPRIVATION SCORES ===")
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

print("\n=== 5. EXTRACTING FORCE CENTROID COORDINATES ===")
coords_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    print(f"Reading coordinates from {pf}...")
    df_coords = pd.read_parquet(pf, columns=["reported_by", "latitude", "longitude"]).dropna()
    coords_list.append(df_coords)

df_all_coords = pd.concat(coords_list).groupby("reported_by")[["latitude", "longitude"]].mean().reset_index()
df_all_coords["police_force"] = df_all_coords["reported_by"].map(map_street_force_to_excel)
df_all_coords = df_all_coords.dropna(subset=["police_force"])
df_force_coords = df_all_coords.groupby("police_force")[["latitude", "longitude"]].mean().reset_index()
print(f"Computed geographical coordinates for {len(df_force_coords)} forces.")
print(df_force_coords.head(10))

print("\n=== 6. CALCULATING NET CRIME HARM (CHI) PER FORCE ===")
counts_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    print(f"Reading counts from {pf}...")
    df_chunk = pd.read_parquet(pf, columns=["reported_by", "crime_type"]).dropna()
    counts = df_chunk.groupby(["reported_by", "crime_type"]).size().reset_index(name="count")
    counts_list.append(counts)

df_all_counts = pd.concat(counts_list).groupby(["reported_by", "crime_type"])["count"].sum().reset_index()
df_all_counts["police_force"] = df_all_counts["reported_by"].map(map_street_force_to_excel)
df_all_counts = df_all_counts.dropna(subset=["police_force"])

# Align crime types to CCHI medians
crime_to_docx = {
    "Violence and sexual offences": "Violence and sexual offences",
    "Public order": "Public order",
    "Criminal damage and arson": "Criminal damage and arson",
    "Other theft": "Other theft",
    "Shoplifting": "Shoplifting",
    "Vehicle crime": "Vehicle crime",
    "Burglary": "Burglary",
    "Drugs": "Drugs",
    "Other crime": "Other crime",
    "Theft from the person": "Theft from the person",
    "Robbery": "Robbery",
    "Bicycle theft": "Bicycle theft",
    "Possession of weapons": "Possession of weapons",
    "Anti-social behaviour": "Anti-social behaviour"
}

df_all_counts["median_score"] = df_all_counts["crime_type"].map(crime_to_docx).map(category_medians)
df_all_counts["total_chi"] = df_all_counts["count"] * df_all_counts["median_score"]

df_chi = df_all_counts.groupby("police_force")["total_chi"].sum().reset_index()
print(f"Calculated Total CHI (net aggregated) for {len(df_chi)} forces.")

print("\n=== 7. MERGING SPATIAL DATASETS AND SPATIAL WEIGHTS MATRIX ===")
df_spatial = pd.merge(df_deprivation, df_chi, on="police_force")
df_spatial = pd.merge(df_spatial, df_force_coords, on="police_force")

# Construct Spatial Weights Matrix (W) using KNN where K=3
n_forces = len(df_spatial)
W = np.zeros((n_forces, n_forces))

coords = df_spatial[["latitude", "longitude"]].values

for i in range(n_forces):
    dists = []
    for j in range(n_forces):
        if i == j:
            dists.append(np.inf) # Avoid self-adjacency
        else:
            # Simple Euclidean distance for adjacency
            dist = np.sqrt(np.sum((coords[i] - coords[j])**2))
            dists.append(dist)
            
    # Find the indices of the K=3 nearest neighbors
    nearest_neighbors = np.argsort(dists)[:3]
    
    # Set weights
    W[i, nearest_neighbors] = 1.0
    
# Row-standardize W so row weights sum exactly to 1.0
row_sums = W.sum(axis=1)
for i in range(n_forces):
    if row_sums[i] > 0:
        W[i, :] = W[i, :] / row_sums[i]

# Compute spatial lag of CHI (W * y)
y = df_spatial["total_chi"].values
spatial_lag_chi = np.dot(W, y)

df_spatial["spatial_lag_chi"] = spatial_lag_chi
print("Successfully computed 'spatial_lag_chi' feature.")
print(df_spatial[["police_force", "latitude", "longitude", "total_chi", "spatial_lag_chi"]].head(10))
