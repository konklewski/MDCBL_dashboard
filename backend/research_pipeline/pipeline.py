from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docx
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "cache"
REPORT_DIR = ROOT / "report"
FEEDBACK_DIR = ROOT / "feedback"
FRONTEND_DATA = ROOT.parents[1] / "src" / "data" / "researchSnapshot.generated.ts"

CRIME_DOC = ROOT / "Crime severity scores.docx"
POLICE_XLSX = ROOT / "Police force in England.xlsx"
IOD_XLSX = ROOT / "data" / "File_5_IoD2019_Scores.xlsx"
TRANSFERS_CSV = REPORT_DIR / "optimized_officer_transfers.csv"
TRANSFERS_2026_CSV = REPORT_DIR / "optimized_officer_transfers_2026.csv"
TARGETS_2026_CSV = REPORT_DIR / "reallocation_targets_2026.csv"
LSOA_HARM_SURFACE_CSV = REPORT_DIR / "lsoa_harm_surface.csv"

STREET_FILES = [ROOT / "data" / "street_from_2018.parquet", ROOT / "data" / "street_from_2021.parquet"]
STOP_SEARCH_FILES = [ROOT / "data" / "stop_and_search_from_2021.parquet"]

FORCE_CODES = {
    "Avon & Somerset": "AVS",
    "Bedfordshire": "BED",
    "Cambridgeshire": "CAM",
    "Cheshire": "CHE",
    "City of London": "COL",
    "Cleveland": "CLE",
    "Cumbria": "CUM",
    "Derbyshire": "DER",
    "Devon & Cornwall": "DEC",
    "Dorset": "DOR",
    "Durham": "DUR",
    "Essex": "ESX",
    "Gloucestershire": "GLO",
    "Greater Manchester": "GMP",
    "Hampshire": "HAM",
    "Hampshire & Isle of Wight": "HAM",
    "Hertfordshire": "HER",
    "Humberside": "HUM",
    "Kent": "KEN",
    "Lancashire": "LAN",
    "Leicestershire": "LEI",
    "Lincolnshire": "LIN",
    "Merseyside": "MER",
    "Metropolitan Police": "MPS",
    "Norfolk": "NOR",
    "North Yorkshire": "NYP",
    "Northamptonshire": "NHA",
    "Northumbria": "NUM",
    "Nottinghamshire": "NOT",
    "South Yorkshire": "SYP",
    "Staffordshire": "STA",
    "Suffolk": "SUF",
    "Surrey": "SUR",
    "Sussex": "SUS",
    "Thames Valley": "TVP",
    "Warwickshire": "WAR",
    "West Mercia": "WMC",
    "West Midlands": "WMP",
    "West Yorkshire": "WYP",
    "Wiltshire": "WIL",
}

UNSUPPORTED_FORCES = ["South Wales", "Gwent", "North Wales", "Dyfed-Powys", "Police Scotland (advisory)"]

KNOWN_CATEGORIES = [
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
    "Violence and sexual offences",
]

CRIME_TO_DOCX = {
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


def map_street_force_to_excel(street_force: str | None) -> str | None:
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
        "Hampshire Constabulary": "Hampshire",
        "Hertfordshire Constabulary": "Hertfordshire",
        "Humberside Police": "Humberside",
        "Kent Police": "Kent",
        "Lancashire Constabulary": "Lancashire",
        "Leicestershire Police": "Leicestershire",
        "Lincolnshire Police": "Lincolnshire",
        "Metropolitan Police Service": "Metropolitan Police",
        "City of London Police": "City of London",
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
    return mapping.get(street_force or "")


def clean_number(value: Any) -> int | float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    return value


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def parse_crime_severity_medians() -> dict[str, float]:
    doc = docx.Document(CRIME_DOC)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    medians: dict[str, float] = {}
    for i, text in enumerate(paragraphs[:-1]):
        matched = next((cat for cat in KNOWN_CATEGORIES if text.lower().startswith(cat.lower())), None)
        if not matched:
            continue
        next_text = paragraphs[i + 1]
        score = None
        for pattern in [r"median\s*[–-]\s*([\d,]+)", r"score of\s*([\d,]+)", r"have a score of\s*([\d,]+)"]:
            match = re.search(pattern, next_text)
            if match:
                score = float(match.group(1).replace(",", "."))
                break
        if score is not None:
            medians[matched] = score
    if "Anti-social behavior" in medians:
        medians["Anti-social behaviour"] = medians["Anti-social behavior"]
    return medians


def load_baselines() -> pd.DataFrame:
    df = pd.read_excel(POLICE_XLSX, sheet_name="Territorial Forces")
    df = df.iloc[3:].dropna(subset=["Unnamed: 0"])
    df = df.rename(columns={"Unnamed: 0": "police_force", "Unnamed: 2": "headcount_baseline", "Unnamed: 3": "core_grant"})
    df = df[~df["police_force"].isin(["England total", "Forces listed"])]
    df["headcount_baseline"] = df["headcount_baseline"].astype(int)
    df["core_grant"] = df["core_grant"].astype(float)
    return df[["police_force", "headcount_baseline", "core_grant"]].sort_values("police_force")


def load_existing_transfers() -> pd.DataFrame:
    rows = []
    with TRANSFERS_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "origin": row["Origin"],
                    "destination": row["Destination"],
                    "headcount": int(float(row["Headcount shifted"])),
                    "haversineMiles": float(row["Haversine Distance"]),
                    "officerMiles": float(row["total Officer-Miles"]),
                }
            )
    return pd.DataFrame(rows)


def parse_markdown_number(text: str, label: str) -> float | None:
    pattern = re.escape(label) + r".*?\*\*([0-9,]+(?:\.[0-9]+)?)"
    match = re.search(pattern, text, flags=re.S)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def parse_audits() -> dict[str, Any]:
    realloc_path = FEEDBACK_DIR / "reallocation_optimization_audit.md"
    rf_path = FEEDBACK_DIR / "random_forest_audit.md"
    vif_path = FEEDBACK_DIR / "multicollinearity_report.md"
    realloc = realloc_path.read_text(encoding="utf-8") if realloc_path.exists() else ""
    rf = rf_path.read_text(encoding="utf-8") if rf_path.exists() else ""
    vif = vif_path.read_text(encoding="utf-8") if vif_path.exists() else ""
    forecast_path = FEEDBACK_DIR / "forecasting_model_evaluation.md"
    stop_search_path = FEEDBACK_DIR / "stop_search_efficiency_report.md"
    realloc_2026_path = FEEDBACK_DIR / "reallocation_optimization_audit_2026.md"
    return {
        "reallocation": {
            "nationalPoolFTE": parse_markdown_number(realloc, "Total National Pool of Available Officers"),
            "totalOfficersReallocated": parse_markdown_number(realloc, "Total Officers Reallocated"),
            "redistributionRatePct": parse_markdown_number(realloc, "Redistribution Rate"),
            "minimizedOfficerMiles": parse_markdown_number(realloc, "Minimized Logistical Footprint"),
            "averageTransferDistanceMiles": parse_markdown_number(realloc, "Average Transfer Distance"),
            "solverStatus": "Optimization terminated successfully. (HiGHS Status 7: Optimal)"
            if "HiGHS Status 7: Optimal" in realloc
            else None,
        },
        "randomForestAuditTextAvailable": bool(rf.strip()),
        "vifAuditTextAvailable": bool(vif.strip()),
        "forecastingModelEvaluationTextAvailable": forecast_path.exists() and bool(forecast_path.read_text(encoding="utf-8").strip()),
        "stopSearchEfficiencyTextAvailable": stop_search_path.exists() and bool(stop_search_path.read_text(encoding="utf-8").strip()),
        "reallocation2026TextAvailable": realloc_2026_path.exists() and bool(realloc_2026_path.read_text(encoding="utf-8").strip()),
    }


def load_transfers(path: Path) -> pd.DataFrame:
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if "FTE shifted" in row:
                rows.append(
                    {
                        "origin": row["Origin"],
                        "destination": row["Destination"],
                        "headcount": int(float(row["FTE shifted"])),
                        "haversineMiles": float(row["Haversine distance miles"]),
                        "officerMiles": float(row["Total officer-miles"]),
                    }
                )
            else:
                rows.append(
                    {
                        "origin": row["Origin"],
                        "destination": row["Destination"],
                        "headcount": int(float(row["Headcount shifted"])),
                        "haversineMiles": float(row["Haversine Distance"]),
                        "officerMiles": float(row["total Officer-Miles"]),
                    }
                )
    return pd.DataFrame(rows)


def load_deprivation_from_lsoa_surface() -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    if not LSOA_HARM_SURFACE_CSV.exists() or not IOD_XLSX.exists():
        return {}, {"income": None, "health": None, "education": None, "housing": None, "services": None}

    lsoa_force = pd.read_csv(LSOA_HARM_SURFACE_CSV, usecols=["police_force", "lsoa_code"])
    lsoa_force = lsoa_force.dropna().drop_duplicates(subset=["lsoa_code"])
    iod = pd.read_excel(IOD_XLSX, sheet_name="IoD2019 Scores").rename(
        columns={
            "LSOA code (2011)": "lsoa_code",
            "Income Score (rate)": "income_score",
            "Education, Skills and Training Score": "education_score",
            "Health Deprivation and Disability Score": "health_score",
            "Barriers to Housing and Services Score": "housing_score",
        }
    )
    cols = ["income_score", "education_score", "health_score", "housing_score"]
    merged = iod[["lsoa_code", *cols]].merge(lsoa_force, on="lsoa_code", how="inner")
    by_force = merged.groupby("police_force")[cols].mean()
    force_imd = {
        force: {
            "income": float(row["income_score"]),
            "health": float(row["health_score"]),
            "education": float(row["education_score"]),
            "housing": float(row["housing_score"]),
            "services": None,
        }
        for force, row in by_force.iterrows()
    }
    national = merged[cols].mean()
    national_imd = {
        "income": float(national["income_score"]),
        "health": float(national["health_score"]),
        "education": float(national["education_score"]),
        "housing": float(national["housing_score"]),
        "services": None,
    }
    return force_imd, national_imd


def load_lsoa_summaries() -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    if not LSOA_HARM_SURFACE_CSV.exists():
        return {}, {}

    cols = [
        "police_force",
        "lsoa_code",
        "lsoa_name",
        "latitude",
        "longitude",
        "crime_count",
        "crime_harm",
        "spatial_demand_score",
        "suggested_lsoa_officers",
    ]
    lsoa = pd.read_csv(LSOA_HARM_SURFACE_CSV, usecols=cols).dropna(subset=["police_force", "lsoa_code"])
    lsoa = lsoa.sort_values(["police_force", "spatial_demand_score"], ascending=[True, False])

    top_lsoas: dict[str, list[dict[str, Any]]] = defaultdict(list)
    heat_cells: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for force, group in lsoa.groupby("police_force"):
        for _, row in group.head(10).iterrows():
            top_lsoas[force].append(
                {
                    "name": row["lsoa_name"],
                    "code": row["lsoa_code"],
                    "latitude": clean_number(row["latitude"]),
                    "longitude": clean_number(row["longitude"]),
                    "scores": {
                        "Demand score": float(row["spatial_demand_score"]),
                        "Crime harm": float(row["crime_harm"]),
                        "Suggested officers": int(round(row["suggested_lsoa_officers"])),
                        "Crime count": int(round(row["crime_count"])),
                    },
                }
            )
        for _, row in group.head(80).iterrows():
            heat_cells[force].append(
                {
                    "name": row["lsoa_name"],
                    "code": row["lsoa_code"],
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "demandScore": float(row["spatial_demand_score"]),
                    "crimeHarm": float(row["crime_harm"]),
                    "suggestedOfficers": int(round(row["suggested_lsoa_officers"])),
                }
            )

    return dict(top_lsoas), dict(heat_cells)


def build_snapshot_from_clean_outputs() -> dict[str, Any]:
    medians = parse_crime_severity_medians()
    targets = pd.read_csv(TARGETS_2026_CSV)
    transfers = load_transfers(TRANSFERS_2026_CSV)
    audits = parse_audits()
    force_imd, national_imd = load_deprivation_from_lsoa_surface()
    top_lsoas, heat_cells = load_lsoa_summaries()

    force_rows = []
    for _, row in targets.sort_values("police_force").iterrows():
        name = row["police_force"]
        net = int(round(row["delta_fte"]))
        hit_rate = clean_number(row.get("hit_rate"))
        predicted_chi = clean_number(row.get("predicted_chi_2026"))
        force_rows.append(
            {
                "id": FORCE_CODES.get(name, name[:3].upper()),
                "name": name,
                "code": FORCE_CODES.get(name, name[:3].upper()),
                "baselineFTE": int(round(row["officer_fte_2025"])),
                "proposedFTE": int(round(row["final_target_fte"])),
                "netShift": net,
                "status": "deficit" if net > 0 else "surplus" if net < 0 else "balanced",
                "coreGrant2025_26": float(row["core_grant_2025"]),
                "areaSqMi": None,
                "populationDensity": None,
                "safetyIndex": None,
                "crimeByCategory": {},
                "imd": force_imd.get(name, {"income": None, "health": None, "education": None, "housing": None, "services": None}),
                "topLsoas": top_lsoas.get(name, []),
                "lsoaDemandCells": heat_cells.get(name, []),
                "research": {
                    "totalChi": None,
                    "predictedChi": predicted_chi,
                    "spatialLagChi": None,
                    "hitRate": hit_rate,
                    "successCount": None,
                    "searchCount": None,
                    "latitude": None,
                    "longitude": None,
                    "sourceCompleteness": "clean_2026_forecast_outputs",
                },
                "missingComputedFields": [
                    "observedTotalChiSerializedInTargets",
                    "spatialLagChiSerializedInTargets",
                    "stopSearchSuccessCount",
                    "stopSearchTotalCount",
                    "crimeCategoryCounts",
                    "forceCentroid",
                    "areaSqMi",
                    "populationDensity",
                    "safetyIndex",
                    "lloydInternalAllocation",
                ],
                "allocationNote": row.get("allocation_note"),
            }
        )

    return {
        "schemaVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "clean-2026-forecast",
        "sourceFiles": {
            "crimeSeverityDocx": str(CRIME_DOC.relative_to(ROOT)),
            "cleanForecastScript": "forecast_and_reallocate_2026.py",
            "optimizedTransfersCsv": str(TRANSFERS_2026_CSV.relative_to(ROOT)),
            "reallocationTargetsCsv": str(TARGETS_2026_CSV.relative_to(ROOT)),
            "lsoaHarmSurfaceCsv": str(LSOA_HARM_SURFACE_CSV.relative_to(ROOT)) if LSOA_HARM_SURFACE_CSV.exists() else None,
            "rawParquetDirectory": "data/",
        },
        "computationTruth": {
            "cacheBuiltFromExistingOutputs": True,
            "fullRawRecomputeImplemented": True,
            "fullRawRecomputeExecutedForThisCache": False,
            "allocationChiBasis": "predicted_chi_2026",
            "predictionModel": "RandomForestRegressor yearly 2026 CHI forecast using 2021-2025 force-year panel, previous-year CHI, lagged spatial lag, and force-level deprivation features.",
            "stopSearchAdjustment": "Force-level hit_rate from forecast_and_reallocate_2026.py, clipped to 0.75-1.25 relative multiplier inside reallocation.",
            "linearProgramming": "2026 transfer CSV produced by spatial balanced transportation LP minimizing Haversine officer-miles.",
            "knownLimitations": [
                "Targets CSV stores hit_rate percentage but not successful_searches/search_count by force.",
                "Targets CSV stores predicted_chi_2026 but not observed total_chi or spatial_lag_chi columns.",
                "LSOA harm surface exists in backend report folder but is not exposed to frontend graph endpoints yet.",
            ],
        },
        "scope": {
            "computedForces": len(force_rows),
            "forceScope": "English territorial forces from cleaned 2026 model outputs; Metropolitan Police and City of London are separate.",
            "unsupportedForces": UNSUPPORTED_FORCES,
        },
        "crimeSeverityMedians": medians,
        "nationalAvgImd": national_imd,
        "audits": audits,
        "missingData": [
            {
                "id": "lloyd_internal_lsoa_allocation",
                "status": "not_implemented",
                "reason": "No research file contains station capacity constraints, response-time objective, or Lloyd/k-means deployment output.",
            },
            {
                "id": "frontend_lsoa_heatmap_endpoint",
                "status": "not_implemented",
                "reason": "Clean LSOA harm surface CSV exists, but no frontend endpoint/layer has been built yet.",
            },
            {
                "id": "stop_search_force_counts",
                "status": "not_serialized",
                "reason": "Current 2026 target CSV includes hit_rate but not successful/total search counts per force.",
            },
            {
                "id": "wales_scotland_scope",
                "status": "not_in_current_computation",
                "reason": "Clean force-name mapper covers English forces only.",
            },
        ],
        "forces": force_rows,
        "transfers": transfers.to_dict(orient="records"),
    }


def build_snapshot_from_existing() -> dict[str, Any]:
    if TARGETS_2026_CSV.exists() and TRANSFERS_2026_CSV.exists():
        return build_snapshot_from_clean_outputs()

    medians = parse_crime_severity_medians()
    baselines = load_baselines()
    transfers = load_existing_transfers()
    audits = parse_audits()

    inflow = transfers.groupby("destination")["headcount"].sum().to_dict()
    outflow = transfers.groupby("origin")["headcount"].sum().to_dict()
    force_rows = []

    for _, row in baselines.iterrows():
        name = row["police_force"]
        net = int(inflow.get(name, 0)) - int(outflow.get(name, 0))
        status = "deficit" if net > 0 else "surplus" if net < 0 else "balanced"
        force_rows.append(
            {
                "id": FORCE_CODES.get(name, name[:3].upper()),
                "name": name,
                "code": FORCE_CODES.get(name, name[:3].upper()),
                "baselineFTE": int(row["headcount_baseline"]),
                "proposedFTE": int(row["headcount_baseline"]) + net,
                "netShift": net,
                "status": status,
                "coreGrant2025_26": float(row["core_grant"]),
                "areaSqMi": None,
                "populationDensity": None,
                "safetyIndex": None,
                "crimeByCategory": {},
                "imd": {"income": None, "health": None, "education": None, "housing": None, "services": None},
                "topLsoas": [],
                "research": {
                    "totalChi": None,
                    "predictedChi": None,
                    "spatialLagChi": None,
                    "hitRate": None,
                    "successCount": None,
                    "searchCount": None,
                    "latitude": None,
                    "longitude": None,
                    "sourceCompleteness": "partial_from_existing_reports",
                },
                "missingComputedFields": [
                    "totalChi",
                    "predictedChi",
                    "spatialLagChi",
                    "hitRate",
                    "deprivationScores",
                    "crimeCategoryCounts",
                    "topLsoas",
                    "forceCentroid",
                ],
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "from-existing",
        "sourceFiles": {
            "crimeSeverityDocx": str(CRIME_DOC.relative_to(ROOT)),
            "policeBaselineXlsx": str(POLICE_XLSX.relative_to(ROOT)),
            "optimizedTransfersCsv": str(TRANSFERS_CSV.relative_to(ROOT)),
            "rawParquetDirectory": "data/",
        },
        "computationTruth": {
            "cacheBuiltFromExistingOutputs": True,
            "allocationDemandSignal": "predicted_chi_2026 from forecast_and_reallocate_2026.py",
        },
        "scope": {
            "computedForces": len(force_rows),
            "forceScope": "England territorial forces from Police force in England.xlsx; London merges Metropolitan Police + City of London Police.",
            "unsupportedForces": UNSUPPORTED_FORCES,
        },
        "crimeSeverityMedians": medians,
        "audits": audits,
        "missingData": [
            {
                "id": "lloyd_internal_lsoa_allocation",
                "status": "not_implemented",
                "reason": "No research file contains LSOA-level officer placement targets, station capacity constraints, response-time objective, or Lloyd/k-means allocation output.",
            },
            {
                "id": "cached_per_force_model_inputs",
                "status": "requires_full_recompute",
                "reason": "Existing report folder contains transfer CSV and markdown audits, not serialized per-force CHI, IMD, hit-rate, centroid, or predicted-CHI rows.",
            },
            {
                "id": "wales_scotland_scope",
                "status": "not_in_current_computation",
                "reason": "Legacy force-name mapper covers English forces only; Welsh forces and Police Scotland advisory are not valid computed outputs.",
            },
        ],
        "forces": force_rows,
        "transfers": transfers.to_dict(orient="records"),
    }


def build_lsoa_force_map() -> tuple[dict[str, str], pd.DataFrame]:
    lsoa_force_map: dict[str, str] = {}
    coords = []
    for path in STREET_FILES:
        df = pd.read_parquet(path, columns=["lsoa_code", "reported_by", "latitude", "longitude"])
        mapping = df.dropna(subset=["lsoa_code", "reported_by"]).groupby("lsoa_code")["reported_by"].agg(lambda x: x.value_counts().index[0])
        lsoa_force_map.update(mapping.to_dict())
        coords.append(df[["lsoa_code", "latitude", "longitude"]].dropna())
    df_coords = pd.concat(coords).groupby("lsoa_code")[["latitude", "longitude"]].mean().reset_index()
    return lsoa_force_map, df_coords


def compute_full_snapshot() -> dict[str, Any]:
    from scipy.optimize import linprog
    from scipy.spatial import cKDTree
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import KFold

    medians = parse_crime_severity_medians()
    baselines = load_baselines()
    lsoa_force_map, df_lsoa_coords = build_lsoa_force_map()

    df_iod = pd.read_excel(IOD_XLSX, sheet_name="IoD2019 Scores").rename(
        columns={
            "LSOA code (2011)": "lsoa_code",
            "Income Score (rate)": "income_score",
            "Education, Skills and Training Score": "education_score",
            "Health Deprivation and Disability Score": "health_score",
            "Barriers to Housing and Services Score": "housing_score",
        }
    )
    df_iod["street_force"] = df_iod["lsoa_code"].map(lsoa_force_map)
    df_iod["police_force"] = df_iod["street_force"].map(map_street_force_to_excel)
    deprivation = df_iod.dropna(subset=["police_force"]).groupby("police_force")[
        ["income_score", "education_score", "health_score", "housing_score"]
    ].mean().reset_index()

    coords = []
    for path in STREET_FILES:
        coords.append(pd.read_parquet(path, columns=["reported_by", "latitude", "longitude"]).dropna())
    force_coords = pd.concat(coords).groupby("reported_by")[["latitude", "longitude"]].mean().reset_index()
    force_coords["police_force"] = force_coords["reported_by"].map(map_street_force_to_excel)
    force_coords = force_coords.dropna(subset=["police_force"]).groupby("police_force")[["latitude", "longitude"]].mean().reset_index()

    street_2025 = pd.read_parquet(STREET_FILES[1], columns=["lsoa_code", "reported_by", "month", "crime_type"])
    street_2025 = street_2025[street_2025["month"].between("2025-01", "2025-12")].dropna()
    counts = street_2025.groupby(["reported_by", "crime_type"]).size().reset_index(name="count")
    counts["police_force"] = counts["reported_by"].map(map_street_force_to_excel)
    counts = counts.dropna(subset=["police_force"])
    counts["median_score"] = counts["crime_type"].map(CRIME_TO_DOCX).map(medians)
    counts["total_chi"] = counts["count"] * counts["median_score"]
    chi = counts.groupby("police_force")["total_chi"].sum().reset_index()
    crime_by_category = counts.pivot_table(index="police_force", columns="crime_type", values="count", aggfunc="sum", fill_value=0)

    spatial = deprivation.merge(chi, on="police_force").merge(force_coords, on="police_force")
    coords_np = spatial[["latitude", "longitude"]].values
    n_forces = len(spatial)
    weights = np.zeros((n_forces, n_forces))
    for i in range(n_forces):
        dists = np.sqrt(np.sum((coords_np[i] - coords_np) ** 2, axis=1))
        dists[i] = np.inf
        weights[i, np.argsort(dists)[:3]] = 1.0
    weights = weights / weights.sum(axis=1, keepdims=True)
    spatial["spatial_lag_chi"] = weights.dot(spatial["total_chi"].values)

    features = ["income_score", "education_score", "health_score", "housing_score", "spatial_lag_chi"]
    x = spatial[features].values
    y = spatial["total_chi"].values
    cv_results = []
    for fold, (train_idx, test_idx) in enumerate(KFold(n_splits=5, shuffle=True, random_state=42).split(x), start=1):
        model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
        model.fit(x[train_idx], y[train_idx])
        pred = model.predict(x[test_idx])
        cv_results.append({"fold": fold, "r2": r2_score(y[test_idx], pred), "rmse": np.sqrt(mean_squared_error(y[test_idx], pred)), "mae": mean_absolute_error(y[test_idx], pred)})
    rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
    rf.fit(x, y)
    spatial["predicted_chi"] = rf.predict(x)
    importances = dict(zip(features, rf.feature_importances_))

    ss = pd.read_parquet(STOP_SEARCH_FILES[0], columns=["latitude", "longitude", "outcome", "outcome_linked_to_object_of_search"]).dropna(subset=["latitude", "longitude"])
    tree = cKDTree(df_lsoa_coords[["latitude", "longitude"]].values)
    _, idx = tree.query(ss[["latitude", "longitude"]].values)
    ss["lsoa_code"] = df_lsoa_coords.iloc[idx]["lsoa_code"].values
    ss["street_force"] = ss["lsoa_code"].map(lsoa_force_map)
    ss["police_force"] = ss["street_force"].map(map_street_force_to_excel)
    ss = ss.dropna(subset=["police_force"])
    ss["success"] = ss.apply(lambda r: "arrest" in str(r["outcome"]).lower() or r["outcome_linked_to_object_of_search"] is True, axis=1)
    success = ss.groupby("police_force")["success"].agg(["sum", "count"]).reset_index().rename(columns={"sum": "success_count", "count": "search_count"})
    success["hit_rate"] = success["success_count"] / success["search_count"]
    national_hit_rate = ss["success"].mean()

    merged = spatial.merge(success, on="police_force").merge(baselines, on="police_force")
    pool = merged["headcount_baseline"].sum()
    allocation_chi = "total_chi"
    merged["baseline_target"] = pool * (merged[allocation_chi] / merged[allocation_chi].sum())
    merged["multiplier"] = merged["hit_rate"] / national_hit_rate
    merged["adjusted_target"] = merged["baseline_target"] * merged["multiplier"]
    merged["scaled_target"] = merged["adjusted_target"] * (pool / merged["adjusted_target"].sum())
    merged["floor_target"] = np.floor(merged["scaled_target"]).astype(int)
    residual = int(pool - merged["floor_target"].sum())
    merged["fractional_remainder"] = merged["scaled_target"] - merged["floor_target"]
    merged = merged.sort_values("fractional_remainder", ascending=False)
    merged["final_target"] = merged["floor_target"]
    merged.iloc[:residual, merged.columns.get_loc("final_target")] += 1
    merged["delta"] = merged["final_target"] - merged["headcount_baseline"]

    surplus = merged[merged["delta"] < 0].copy()
    deficit = merged[merged["delta"] > 0].copy()
    surplus["supply"] = surplus["delta"].abs().astype(int)
    deficit["demand"] = deficit["delta"].astype(int)
    cost = np.zeros((len(surplus), len(deficit)))
    for i, source in surplus.reset_index(drop=True).iterrows():
        for j, dest in deficit.reset_index(drop=True).iterrows():
            cost[i, j] = haversine_miles(source["latitude"], source["longitude"], dest["latitude"], dest["longitude"])
    a_eq, b_eq = [], []
    for i in range(len(surplus)):
        row = np.zeros_like(cost)
        row[i, :] = 1.0
        a_eq.append(row.flatten())
        b_eq.append(surplus.iloc[i]["supply"])
    for j in range(len(deficit)):
        row = np.zeros_like(cost)
        row[:, j] = 1.0
        a_eq.append(row.flatten())
        b_eq.append(deficit.iloc[j]["demand"])
    res = linprog(cost.flatten(), A_eq=np.array(a_eq), b_eq=np.array(b_eq), bounds=(0, None), method="highs")
    opt = res.x.reshape(len(surplus), len(deficit))
    transfers = []
    for i in range(len(surplus)):
        for j in range(len(deficit)):
            flow = round(opt[i, j])
            if flow > 0:
                dist = cost[i, j]
                transfers.append({"origin": surplus.iloc[i]["police_force"], "destination": deficit.iloc[j]["police_force"], "headcount": int(flow), "haversineMiles": float(dist), "officerMiles": float(flow * dist)})
    transfers = sorted(transfers, key=lambda row: row["officerMiles"], reverse=True)

    force_rows = []
    for _, row in merged.sort_values("police_force").iterrows():
        name = row["police_force"]
        cats = crime_by_category.loc[name].to_dict() if name in crime_by_category.index else {}
        force_rows.append(
            {
                "id": FORCE_CODES.get(name, name[:3].upper()),
                "name": name,
                "code": FORCE_CODES.get(name, name[:3].upper()),
                "baselineFTE": int(row["headcount_baseline"]),
                "proposedFTE": int(row["final_target"]),
                "netShift": int(row["delta"]),
                "status": "deficit" if row["delta"] > 0 else "surplus" if row["delta"] < 0 else "balanced",
                "coreGrant2025_26": float(row["core_grant"]),
                "areaSqMi": None,
                "populationDensity": None,
                "safetyIndex": None,
                "crimeByCategory": {str(k): int(v) for k, v in cats.items()},
                "imd": {
                    "income": float(row["income_score"]),
                    "health": float(row["health_score"]),
                    "education": float(row["education_score"]),
                    "housing": float(row["housing_score"]),
                    "services": None,
                },
                "topLsoas": [],
                "research": {
                    "totalChi": float(row["total_chi"]),
                    "predictedChi": float(row["predicted_chi"]),
                    "spatialLagChi": float(row["spatial_lag_chi"]),
                    "hitRate": float(row["hit_rate"]),
                    "successCount": int(row["success_count"]),
                    "searchCount": int(row["search_count"]),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                    "sourceCompleteness": "full_recompute",
                },
                "missingComputedFields": ["areaSqMi", "populationDensity", "safetyIndex", "topLsoas", "lloydInternalAllocation"],
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "full",
        "sourceFiles": {"crimeSeverityDocx": "Crime severity scores.docx", "policeBaselineXlsx": "Police force in England.xlsx", "rawParquetDirectory": "data/"},
        "computationTruth": {
            "cacheBuiltFromExistingOutputs": False,
            "fullRawRecomputeImplemented": True,
            "fullRawRecomputeExecutedForThisCache": True,
            "allocationChiBasis": allocation_chi,
            "knownResearchInconsistency": "Legacy audit text says Random Forest predicted CHI feeds allocation, but legacy run_reallocation.py uses observed total_chi. This full backend preserves observed total_chi allocation to reproduce research CSV semantics.",
        },
        "scope": {"computedForces": len(force_rows), "forceScope": "English mapped territorial forces", "unsupportedForces": UNSUPPORTED_FORCES},
        "crimeSeverityMedians": medians,
        "audits": {
            "randomForest": {"cv": cv_results, "featureImportances": importances},
            "reallocation": {
                "nationalPoolFTE": int(pool),
                "totalOfficersReallocated": int(sum(t["headcount"] for t in transfers)),
                "minimizedOfficerMiles": float(sum(t["officerMiles"] for t in transfers)),
                "solverStatus": res.message,
                "nationalStopSearchHitRate": float(national_hit_rate),
            },
        },
        "missingData": [
            {"id": "lloyd_internal_lsoa_allocation", "status": "not_implemented", "reason": "No LSOA-level officer placement objective/constraints/output exist in research files."},
            {"id": "wales_scotland_scope", "status": "not_in_current_computation", "reason": "Legacy force-name mapper covers English forces only."},
        ],
        "forces": force_rows,
        "transfers": transfers,
    }


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return float(radius * 2 * np.arcsin(np.sqrt(a)))


def write_outputs(snapshot: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json_safe(snapshot)
    (CACHE_DIR / "research_snapshot.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    FRONTEND_DATA.write_text(
        "/* Generated by backend/research_pipeline/pipeline.py. Do not edit by hand. */\n"
        f"export const researchSnapshot = {json.dumps(payload, indent=2, sort_keys=True)} as const;\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["from-existing", "full"], default="from-existing")
    args = parser.parse_args()
    snapshot = build_snapshot_from_existing() if args.mode == "from-existing" else compute_full_snapshot()
    write_outputs(snapshot)
    print(f"wrote {CACHE_DIR / 'research_snapshot.json'}")
    print(f"wrote {FRONTEND_DATA}")
    print(f"mode={snapshot['mode']} forces={len(snapshot['forces'])} transfers={len(snapshot['transfers'])}")


if __name__ == "__main__":
    main()
