import os
import docx
import re
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import r2_score, mean_squared_error

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
    print(f"Reading LSOA mappings from {pf}...")
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

print("\n=== 5. CALCULATING MONTHLY CRIME HARM (CHI) PER FORCE ===")
counts_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    print(f"Reading incident counts from {pf}...")
    df_chunk = pd.read_parquet(pf, columns=["reported_by", "month", "crime_type"]).dropna()
    counts = df_chunk.groupby(["reported_by", "month", "crime_type"]).size().reset_index(name="count")
    counts_list.append(counts)

df_all_counts = pd.concat(counts_list).groupby(["reported_by", "month", "crime_type"])["count"].sum().reset_index()

# Map reported_by to Excel police_force
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

# Sum CHI per force per month
df_monthly_chi = df_all_counts.groupby(["police_force", "month"])["total_chi"].sum().reset_index()
print(f"Calculated monthly CHI for {len(df_monthly_chi)} force-month observations.")

print("\n=== 6. PANEL MERGE AND FEATURE ENGINEERING ===")
# Merge deprivation scores with monthly CHI
df_panel = pd.merge(df_monthly_chi, df_deprivation, on="police_force")

# Construct lagging features and cyclical features per force
panel_list = []
unique_forces = df_panel["police_force"].unique()

for force in unique_forces:
    df_force = df_panel[df_panel["police_force"] == force].copy()
    df_force = df_force.sort_values("month")
    
    # Extract Month_Of_Year
    df_force["Month_Of_Year"] = df_force["month"].apply(lambda x: int(x.split("-")[1]))
    # Cyclical sin/cos of month of year
    df_force["sin_month"] = np.sin(2 * np.pi * df_force["Month_Of_Year"] / 12)
    df_force["cos_month"] = np.cos(2 * np.pi * df_force["Month_Of_Year"] / 12)
    
    # Lagged features for independent variables at (t-1) and (t-2)
    df_force["income_score_lag1"] = df_force["income_score"].shift(1)
    df_force["income_score_lag2"] = df_force["income_score"].shift(2)
    df_force["education_score_lag1"] = df_force["education_score"].shift(1)
    df_force["education_score_lag2"] = df_force["education_score"].shift(2)
    df_force["health_score_lag1"] = df_force["health_score"].shift(1)
    df_force["health_score_lag2"] = df_force["health_score"].shift(2)
    df_force["housing_score_lag1"] = df_force["housing_score"].shift(1)
    df_force["housing_score_lag2"] = df_force["housing_score"].shift(2)
    df_force["total_chi_lag1"] = df_force["total_chi"].shift(1)
    df_force["total_chi_lag2"] = df_force["total_chi"].shift(2)
    
    # Drop rows with NaN (the first 2 months)
    df_force = df_force.dropna()
    panel_list.append(df_force)

df_panel_clean = pd.concat(panel_list)
print(f"Clean panel dataset has {len(df_panel_clean)} rows across {len(unique_forces)} forces.")

print("\n=== 7. TIME-SERIES TRAINING & VALIDATION PER FORCE ===")
features = [
    "income_score_lag1", "income_score_lag2",
    "education_score_lag1", "education_score_lag2",
    "health_score_lag1", "health_score_lag2",
    "housing_score_lag1", "housing_score_lag2",
    "total_chi_lag1", "total_chi_lag2",
    "sin_month", "cos_month", "Month_Of_Year"
]

force_metrics = []
for force in unique_forces:
    df_force = df_panel_clean[df_panel_clean["police_force"] == force].copy()
    df_force = df_force.sort_values("month")
    
    if len(df_force) < 10:
        print(f"Skipping {force} due to insufficient observations ({len(df_force)} rows)")
        continue
        
    X_f = df_force[features].values
    y_f = df_force["total_chi"].values
    
    tscv = TimeSeriesSplit(n_splits=5)
    r2_scores = []
    rmse_scores = []
    
    for train_idx, test_idx in tscv.split(X_f):
        X_train, X_test = X_f[train_idx], X_f[test_idx]
        y_train, y_test = y_f[train_idx], y_f[test_idx]
        
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)
        
        y_pred = rf.predict(X_test)
        r2_scores.append(r2_score(y_test, y_pred))
        rmse_scores.append(np.sqrt(mean_squared_error(y_test, y_pred)))
        
    mean_r2 = np.mean(r2_scores)
    mean_rmse = np.mean(rmse_scores)
    
    force_metrics.append({
        "Police_Force": force,
        "Mean_R2": mean_r2,
        "Mean_RMSE": mean_rmse,
        "Observations": len(df_force)
    })
    print(f" - {force}: R² = {mean_r2:.4f}, RMSE = {mean_rmse:.2f} ({len(df_force)} obs)")

df_metrics = pd.DataFrame(force_metrics).sort_values(by="Mean_R2", ascending=False)
print("\nForce-Level Time-Series Forecasting Performance:")
print(df_metrics.head(15))
