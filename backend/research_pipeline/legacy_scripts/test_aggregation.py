import os
import docx
import re
import pandas as pd
import numpy as np

print("=== PROGRAMMATICALLY EXTRACTING CATEGORY MEDIANS ===")
doc = docx.Document("Crime severity scores.docx")
category_medians = {}

current_category = None
for p in doc.paragraphs:
    text = p.text.strip()
    if not text:
        continue
    
    # Check if this is a category paragraph
    if "(" in text and any(cat in text.lower() for cat in ["theft", "burglary", "damage", "drugs", "crime", "weapons", "order", "robbery", "shoplifting", "violence", "behavior"]):
        category_name = text.split("(")[0].strip()
        current_category = category_name
    elif current_category:
        score = None
        # Try to find "median – [digits]" or "median - [digits]"
        median_match = re.search(r'median\s*[–-]\s*([\d,]+)', text)
        if median_match:
            score_str = median_match.group(1).replace(",", ".")
            score = float(score_str)
        else:
            # Try to find "score of [digits]"
            score_match = re.search(r'score of\s*(\d+)', text)
            if score_match:
                score = float(score_match.group(1))
            else:
                # "have a score of 365"
                robbery_match = re.search(r'have a score of\s*(\d+)', text)
                if robbery_match:
                    score = float(robbery_match.group(1))
        
        if score is not None:
            # Clean up the category name to remove any trailing details
            clean_cat = current_category.replace("behavior", "behaviour").strip()
            category_medians[clean_cat] = score
            category_medians[current_category] = score
            current_category = None

print("Extracted Category Medians:")
for cat, score in category_medians.items():
    print(f" - {cat}: {score}")

print("\n=== BUILDING LSOA TO STREET FORCE MAPPING ===")
# To be fast, let's load just a subset or use the columns lsoa_code and reported_by
lsoa_force_map = {}
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    print(f"Reading {pf} for LSOA mapping...")
    # Load only necessary columns in chunks if memory is limited, but pandas can read them quickly
    df = pd.read_parquet(pf, columns=["lsoa_code", "reported_by"]).dropna()
    # Find the most common force for each LSOA
    temp_map = df.groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
    lsoa_force_map.update(temp_map.to_dict())

print(f"Mapped {len(lsoa_force_map)} unique LSOAs to street-level forces.")

print("\n=== MAPPING STREET FORCES TO EXCEL FORCES ===")
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

print("\n=== AGGREGATING DEPRIVATION SCORES ===")
# Load File B
df_b = pd.read_excel("data/File_5_IoD2019_Scores.xlsx", sheet_name="IoD2019 Scores")
df_b = df_b.rename(columns={
    "LSOA code (2011)": "lsoa_code",
    "Income Score (rate)": "income_score",
    "Education, Skills and Training Score": "education_score",
    "Health Deprivation and Disability Score": "health_score",
    "Barriers to Housing and Services Score": "housing_score"
})

# Map each LSOA to Excel force
df_b["street_force"] = df_b["lsoa_code"].map(lsoa_force_map)
df_b["police_force"] = df_b["street_force"].map(map_street_force_to_excel)

df_b_clean = df_b.dropna(subset=["police_force"])
df_deprivation_aggregated = df_b_clean.groupby("police_force")[["income_score", "education_score", "health_score", "housing_score"]].mean().reset_index()

print("Deprivation scores aggregated at force level (shape:", df_deprivation_aggregated.shape, "):")
print(df_deprivation_aggregated.head())

print("\n=== CALCULATING TOTAL CHI PER FORCE ===")
counts_list = []
for pf in ["data/street_from_2018.parquet", "data/street_from_2021.parquet"]:
    print(f"Reading counts from {pf}...")
    df_chunk = pd.read_parquet(pf, columns=["reported_by", "crime_type"]).dropna()
    counts = df_chunk.groupby(["reported_by", "crime_type"]).size().reset_index(name="count")
    counts_list.append(counts)

df_all_counts = pd.concat(counts_list).groupby(["reported_by", "crime_type"])["count"].sum().reset_index()

# Map reported_by to Excel police_force
df_all_counts["police_force"] = df_all_counts["reported_by"].map(map_street_force_to_excel)
df_all_counts = df_all_counts.dropna(subset=["police_force"])

# Direct mapping to docx categories
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

df_chi_aggregated = df_all_counts.groupby("police_force")["total_chi"].sum().reset_index()
print("CHI aggregated at force level (shape:", df_chi_aggregated.shape, "):")
print(df_chi_aggregated.head())

print("\n=== MERGING DATASETS ===")
df_merged = pd.merge(df_deprivation_aggregated, df_chi_aggregated, on="police_force")
print("Merged dataset shape:", df_merged.shape)
print(df_merged.head())
