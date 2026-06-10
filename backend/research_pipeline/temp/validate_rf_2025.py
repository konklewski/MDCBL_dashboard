"""
Temporal Out-of-Sample Validation
Train: 2021-01 to 2024-12  |  Test: 2025-01 to 2025-12
One RF per police force. Reports per-force R² / RMSE.
"""
import os, re, docx, pandas as pd, numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error

os.makedirs("temp", exist_ok=True)

BASE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(BASE, "..")

print("=== 1. CRIME SEVERITY MEDIANS ===")
doc = docx.Document(os.path.join(PIPELINE, "Crime severity scores.docx"))
known_categories = [
    "Anti-social behavior","Bicycle theft","Burglary","Criminal damage and arson",
    "Drugs","Other crime","Other theft","Possession of weapons","Public order",
    "Robbery","Shoplifting","Theft from the person","Vehicle crime",
    "Violence and sexual offences"
]
category_medians = {}
paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
for i, text in enumerate(paragraphs):
    matched_cat = next((c for c in known_categories if text.lower().startswith(c.lower())), None)
    if matched_cat:
        next_text = paragraphs[i + 1]
        for pattern in [r'median\s*[–-]\s*([\d,]+)', r'score of\s*([\d,]+)', r'have a score of\s*([\d,]+)']:
            m = re.search(pattern, next_text)
            if m:
                category_medians[matched_cat] = float(m.group(1).replace(",", "."))
                break
if "Anti-social behavior" in category_medians:
    category_medians["Anti-social behaviour"] = category_medians["Anti-social behavior"]
print(f"  {len(category_medians)} medians parsed.")

print("\n=== 2. FORCE NAME MAP ===")
FORCE_MAP = {
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
    "Wiltshire Police": "Wiltshire",
}

print("\n=== 3. LSOA → FORCE MAPPINGS ===")
lsoa_force_map = {}
for pf in ["street_from_2018.parquet", "street_from_2021.parquet"]:
    path = os.path.join(PIPELINE, "data", pf)
    print(f"  Reading {pf}...")
    df = pd.read_parquet(path, columns=["lsoa_code", "reported_by"]).dropna()
    tmp = df.groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
    lsoa_force_map.update(tmp.to_dict())

print("\n=== 4. DEPRIVATION SCORES ===")
df_b = pd.read_excel(os.path.join(PIPELINE, "data", "File_5_IoD2019_Scores.xlsx"), sheet_name="IoD2019 Scores")
df_b = df_b.rename(columns={
    "LSOA code (2011)": "lsoa_code",
    "Income Score (rate)": "income_score",
    "Education, Skills and Training Score": "education_score",
    "Health Deprivation and Disability Score": "health_score",
    "Barriers to Housing and Services Score": "housing_score",
})
df_b["police_force"] = df_b["lsoa_code"].map(lsoa_force_map).map(FORCE_MAP)
df_deprivation = (
    df_b.dropna(subset=["police_force"])
    .groupby("police_force")[["income_score", "education_score", "health_score", "housing_score"]]
    .mean()
    .reset_index()
)

print("\n=== 5. MONTHLY CHI (2018-2025) ===")
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
    "Anti-social behaviour": "Anti-social behaviour",
}
counts_list = []
for pf in ["street_from_2018.parquet", "street_from_2021.parquet"]:
    path = os.path.join(PIPELINE, "data", pf)
    print(f"  Reading {pf}...")
    df_chunk = pd.read_parquet(path, columns=["reported_by", "month", "crime_type"]).dropna()
    counts = df_chunk.groupby(["reported_by", "month", "crime_type"]).size().reset_index(name="count")
    counts_list.append(counts)

df_all = pd.concat(counts_list).groupby(["reported_by", "month", "crime_type"])["count"].sum().reset_index()
df_all["police_force"] = df_all["reported_by"].map(FORCE_MAP)
df_all = df_all.dropna(subset=["police_force"])
df_all["median_score"] = df_all["crime_type"].map(crime_to_docx).map(category_medians)
df_all["total_chi"] = df_all["count"] * df_all["median_score"]
df_monthly = df_all.groupby(["police_force", "month"])["total_chi"].sum().reset_index()
print(f"  {len(df_monthly)} force-month rows.")

print("\n=== 6. FEATURE ENGINEERING (LAGS + SEASONALITY) ===")
df_panel = pd.merge(df_monthly, df_deprivation, on="police_force")
panel_list = []
for force in df_panel["police_force"].unique():
    df_f = df_panel[df_panel["police_force"] == force].copy().sort_values("month")
    df_f["Month_Of_Year"] = df_f["month"].str[5:7].astype(int)
    df_f["sin_month"] = np.sin(2 * np.pi * df_f["Month_Of_Year"] / 12)
    df_f["cos_month"] = np.cos(2 * np.pi * df_f["Month_Of_Year"] / 12)
    for col in ["income_score", "education_score", "health_score", "housing_score", "total_chi"]:
        df_f[f"{col}_lag1"] = df_f[col].shift(1)
        df_f[f"{col}_lag2"] = df_f[col].shift(2)
    panel_list.append(df_f.dropna())

df_panel_clean = pd.concat(panel_list)

# Temporal split — hard wall at 2025
df_panel_clean["year"] = df_panel_clean["month"].str[:4].astype(int)
df_train_all = df_panel_clean[df_panel_clean["year"].between(2021, 2024)]
df_test_all  = df_panel_clean[df_panel_clean["year"] == 2025]

FEATURES = [
    "income_score_lag1", "income_score_lag2",
    "education_score_lag1", "education_score_lag2",
    "health_score_lag1", "health_score_lag2",
    "housing_score_lag1", "housing_score_lag2",
    "total_chi_lag1", "total_chi_lag2",
    "sin_month", "cos_month", "Month_Of_Year",
]

print(f"\n  Train months: {df_train_all['month'].min()} → {df_train_all['month'].max()}")
print(f"  Test  months: {df_test_all['month'].min()}  → {df_test_all['month'].max()}")

print("\n=== 7. PER-FORCE TEMPORAL VALIDATION (train 2021–2024 / test 2025) ===")
results = []
forces = df_train_all["police_force"].unique()

for force in sorted(forces):
    train = df_train_all[df_train_all["police_force"] == force]
    test  = df_test_all[df_test_all["police_force"] == force]

    if len(train) < 10:
        print(f"  SKIP {force}: only {len(train)} train rows")
        continue
    if len(test) == 0:
        print(f"  SKIP {force}: no 2025 test data")
        continue

    X_train, y_train = train[FEATURES].values, train["total_chi"].values
    X_test,  y_test  = test[FEATURES].values,  test["total_chi"].values

    rf = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)

    r2   = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae  = np.mean(np.abs(y_test - y_pred))

    results.append({
        "Police_Force": force,
        "Train_Rows": len(train),
        "Test_Months": len(test),
        "R2_2025": round(r2, 4),
        "RMSE_2025": round(rmse, 2),
        "MAE_2025": round(mae, 2),
    })
    print(f"  {force:55s}  R²={r2:+.4f}  RMSE={rmse:>14,.0f}  n_test={len(test)}")

df_results = pd.DataFrame(results).sort_values("R2_2025", ascending=False)

print("\n=== 8. SUMMARY ===")
good = (df_results["R2_2025"] > 0).sum()
total = len(df_results)
median_r2 = df_results["R2_2025"].median()
weighted_r2 = np.average(df_results["R2_2025"], weights=df_results["Test_Months"])
print(f"  Forces with R² > 0 : {good}/{total}")
print(f"  Median R²          : {median_r2:.4f}")
print(f"  Weighted mean R²   : {weighted_r2:.4f}")
print(f"\n  Top 5:\n{df_results.head(5)[['Police_Force','R2_2025','RMSE_2025']].to_string(index=False)}")
print(f"\n  Bottom 5:\n{df_results.tail(5)[['Police_Force','R2_2025','RMSE_2025']].to_string(index=False)}")

out_csv = os.path.join(BASE, "per_force_r2_2025.csv")
df_results.to_csv(out_csv, index=False)
print(f"\n  Results saved → {out_csv}")
