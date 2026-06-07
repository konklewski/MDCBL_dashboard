import os
import docx
import re
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import linprog

# Create directories
os.makedirs("report", exist_ok=True)
os.makedirs("feedback", exist_ok=True)

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
coords_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    df = pd.read_parquet(pf, columns=["lsoa_code", "reported_by", "latitude", "longitude"])
    temp_map = df.groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
    lsoa_force_map.update(temp_map.to_dict())
    coords_list.append(df[["lsoa_code", "latitude", "longitude"]].dropna())

df_coords_all = pd.concat(coords_list).groupby("lsoa_code")[["latitude", "longitude"]].mean().reset_index()

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

# Align crime types to CCHI medians (Defined early to prevent NameError)
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

print("\n=== 4. CALCULATING CONTEMPORARY 12-MONTH HARM INDEX (2025) ===")
df_street_2025 = pd.read_parquet("data/street_from_2021.parquet", columns=["reported_by", "month", "crime_type"])
df_street_2025 = df_street_2025[df_street_2025["month"].between("2025-01", "2025-12")].dropna()

counts = df_street_2025.groupby(["reported_by", "crime_type"]).size().reset_index(name="count")
counts["police_force"] = counts["reported_by"].map(map_street_force_to_excel)
counts = counts.dropna(subset=["police_force"])

counts["median_score"] = counts["crime_type"].map(crime_to_docx).map(category_medians)
counts["total_chi"] = counts["count"] * counts["median_score"]

df_chi = counts.groupby("police_force")["total_chi"].sum().reset_index()

print("\n=== 5. MAPPING AND CALCULATING STOP & SEARCH HIT RATES ===")
ss_path = "data/stop_and_search_from_2021.parquet"
df_ss = pd.read_parquet(ss_path, columns=["latitude", "longitude", "outcome", "outcome_linked_to_object_of_search"]).dropna(subset=["latitude", "longitude"])

tree = cKDTree(df_coords_all[["latitude", "longitude"]].values)
ss_coords = df_ss[["latitude", "longitude"]].values
distances, indices = tree.query(ss_coords)
df_ss["lsoa_code"] = df_coords_all.iloc[indices]["lsoa_code"].values

df_ss["street_force"] = df_ss["lsoa_code"].map(lsoa_force_map)
df_ss["police_force"] = df_ss["street_force"].map(map_street_force_to_excel)
df_ss_clean = df_ss.dropna(subset=["police_force"])

def is_success(row):
    outcome = str(row["outcome"]).lower()
    if "arrest" in outcome:
        return True
    if row["outcome_linked_to_object_of_search"] == True:
        return True
    return False

df_ss_clean["success"] = df_ss_clean.apply(is_success, axis=1)

df_success = df_ss_clean.groupby("police_force")["success"].agg(["sum", "count"]).reset_index()
df_success = df_success.rename(columns={"sum": "success_count", "count": "search_count"})
df_success["hit_rate"] = df_success["success_count"] / df_success["search_count"]

national_avg_hit_rate = df_ss_clean["success"].mean()

print("\n=== 6. LOADING FILE C & BASELINE MERGE ===")
df_c = pd.read_excel("Police force in England.xlsx", sheet_name="Territorial Forces")
df_c = df_c.iloc[3:].dropna(subset=["Unnamed: 0"])
df_c = df_c.rename(columns={
    "Unnamed: 0": "police_force",
    "Unnamed: 2": "headcount_baseline",
    "Unnamed: 3": "core_grant"
})
df_c = df_c[~df_c["police_force"].isin(["England total", "Forces listed"])]

df_merged = pd.merge(df_chi, df_success, on="police_force")
df_merged = pd.merge(df_merged, df_c[["police_force", "headcount_baseline", "core_grant"]], on="police_force")
df_merged["headcount_baseline"] = df_merged["headcount_baseline"].astype(int)

# Extract coordinates
df_force_coords = df_coords_all.copy()
df_force_coords["police_force"] = df_force_coords["lsoa_code"].map(lsoa_force_map).map(map_street_force_to_excel)
df_force_coords = df_force_coords.dropna(subset=["police_force"])
df_force_centroids = df_force_coords.groupby("police_force")[["latitude", "longitude"]].mean().reset_index()
df_merged = pd.merge(df_merged, df_force_centroids, on="police_force")

print("\n=== 7. EXECUTING MATHEMATICAL REALLOCATION ENGINE ===")
H_total = df_merged["headcount_baseline"].sum()
print("National Headcount Pool (FTE):", H_total)

total_chi_national = df_merged["total_chi"].sum()
df_merged["baseline_target"] = H_total * (df_merged["total_chi"] / total_chi_national)

df_merged["multiplier"] = df_merged["hit_rate"] / national_avg_hit_rate
df_merged["adjusted_target"] = df_merged["baseline_target"] * df_merged["multiplier"]

# Scale Normalization
df_merged["scaled_target"] = df_merged["adjusted_target"] * (H_total / df_merged["adjusted_target"].sum())

# Initial Integer Allocation
df_merged["floor_target"] = np.floor(df_merged["scaled_target"]).astype(int)

# Residual Allocation
residual_officers = H_total - df_merged["floor_target"].sum()
df_merged["fractional_remainder"] = df_merged["scaled_target"] - df_merged["floor_target"]
df_merged = df_merged.sort_values(by="fractional_remainder", ascending=False)

df_merged["final_target"] = df_merged["floor_target"]
df_merged.iloc[:residual_officers, df_merged.columns.get_loc("final_target")] += 1

# Check final sum matches H_total exactly
final_sum = df_merged["final_target"].sum()
print("Final redistributed sum:", final_sum)
assert final_sum == H_total, "Apportionment sum discrepancy detected!"

df_merged["delta"] = df_merged["final_target"] - df_merged["headcount_baseline"]

print("\n=== 8. SPATIAL LINEAR PROGRAMMING TRANSPORTATION MODEL ===")
# Separate into surplus and deficit forces
surplus_df = df_merged[df_merged["delta"] < 0].copy()
deficit_df = df_merged[df_merged["delta"] > 0].copy()

# Add columns for supply (absolute delta for surplus) and demand
surplus_df["supply"] = surplus_df["delta"].abs().astype(int)
deficit_df["demand"] = deficit_df["delta"].astype(int)

print(f"Surplus Forces (Origins): {len(surplus_df)}")
print(f"Deficit Forces (Destinations): {len(deficit_df)}")
print(f"Total Officers to Shift: {surplus_df['supply'].sum()} (Surplus) | {deficit_df['demand'].sum()} (Deficit)")

# Haversine distance calculator
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 3958.8 # miles
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# Build pairwise cost matrix (haversine distances in miles)
cost_matrix = np.zeros((len(surplus_df), len(deficit_df)))
for i in range(len(surplus_df)):
    for j in range(len(deficit_df)):
        cost_matrix[i, j] = haversine_distance(
            surplus_df.iloc[i]["latitude"], surplus_df.iloc[i]["longitude"],
            deficit_df.iloc[j]["latitude"], deficit_df.iloc[j]["longitude"]
        )

# Formulate LP for scipy
c = cost_matrix.flatten()

A_eq = []
b_eq = []

# Supply constraints
num_origins = len(surplus_df)
num_destinations = len(deficit_df)

for i in range(num_origins):
    row = np.zeros((num_origins, num_destinations))
    row[i, :] = 1.0
    A_eq.append(row.flatten())
    b_eq.append(surplus_df.iloc[i]["supply"])

# Demand constraints
for j in range(num_destinations):
    row = np.zeros((num_origins, num_destinations))
    row[:, j] = 1.0
    A_eq.append(row.flatten())
    b_eq.append(deficit_df.iloc[j]["demand"])

A_eq = np.array(A_eq)
b_eq = np.array(b_eq)

print("Solving spatial transportation LP using Highs solver...")
res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=(0, None), method="highs")
print("Optimization Status:", res.message)

x_opt = res.x.reshape(num_origins, num_destinations)

# Build transfers list
transfers = []
for i in range(num_origins):
    for j in range(num_destinations):
        flow = round(x_opt[i, j])
        if flow > 0:
            dist = cost_matrix[i, j]
            transfers.append({
                "Origin": surplus_df.iloc[i]["police_force"],
                "Destination": deficit_df.iloc[j]["police_force"],
                "Headcount shifted": flow,
                "Haversine Distance": dist,
                "total Officer-Miles": flow * dist
            })

df_transfers = pd.DataFrame(transfers).sort_values(by="total Officer-Miles", ascending=False)
print("\nTop 10 Logistical Shifts:")
print(df_transfers.head(10))

total_shifted = df_transfers["Headcount shifted"].sum()
total_officer_miles = df_transfers["total Officer-Miles"].sum()
print(f"\nOptimization Summary:")
print(f" - Total Officers Reallocated: {total_shifted}")
print(f" - Minimized System Footprint (Total Officer-Miles): {total_officer_miles:.2f} miles")
