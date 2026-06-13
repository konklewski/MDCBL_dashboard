import os
import pandas as pd
import numpy as np

from scipy.spatial import cKDTree
from scipy.optimize import linprog
from sklearn.ensemble import RandomForestRegressor

from crime_severity_scores import CCHI_MEDIAN_SCORES
from force_name_mapping import FORCE_NAME_MAPPING
from police_force_funding import POLICE_FORCE_FUNDING


os.makedirs("report", exist_ok=True)
os.makedirs("feedback", exist_ok=True)

STREET_PATH = "data/street_from_2021.parquet"
STOP_SEARCH_PATH = "data/stop_and_search_from_2021.parquet"
DEPRIVATION_PATH = "data/File_5_IoD2019_Scores.xlsx"

TRANSFERS_PATH = "report/optimized_officer_transfers_2026.csv"
ALLOCATION_TARGETS_PATH = "report/reallocation_targets_2026.csv"
AUDIT_PATH = "feedback/reallocation_optimization_audit_2026.md"


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two latitude-longitude points."""

    radius_miles = 3958.8

    lat1, lon1, lat2, lon2 = map(
        np.radians,
        [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    )

    return radius_miles * 2 * np.arcsin(np.sqrt(a))


def is_success(row):
    """Classify whether a stop and search produced a positive outcome."""

    outcome = str(row["outcome"]).lower()
    linked_to_object = row["outcome_linked_to_object_of_search"]

    if "arrest" in outcome:
        return True

    if linked_to_object is True or str(linked_to_object).lower() == "true":
        return True

    return False


def add_spatial_lag_for_year(year_df):
    """Add the average neighbouring CHI value for each force in one year."""

    year_df = year_df.copy().reset_index(drop=True)

    if len(year_df) < 4:
        raise ValueError(
            "At least 4 police forces are needed to calculate 3 nearest neighbours."
        )

    n_forces = len(year_df)
    coords = year_df[["latitude", "longitude"]].values
    W = np.zeros((n_forces, n_forces))

    # Link each force to its three closest neighbouring forces.
    for i in range(n_forces):
        distances = np.sqrt(((coords - coords[i]) ** 2).sum(axis=1))
        distances[i] = np.inf

        nearest_neighbors = np.argsort(distances)[:3]
        W[i, nearest_neighbors] = 1.0

    # Standardise each row so neighbour weights sum to one.
    row_sums = W.sum(axis=1)
    W = W / row_sums[:, None]

    year_df["spatial_lag_chi"] = W.dot(year_df["total_chi"].values)

    return year_df


def add_baseline_only_forces(df_alloc):
    """Keep forces without modelled demand at their current baseline."""

    existing_forces = set(df_alloc["police_force"])
    fallback_rows = []

    for force, values in POLICE_FORCE_FUNDING.items():
        if force in existing_forces:
            continue

        fallback_rows.append({
            "police_force": force,
            "predicted_chi_2026": np.nan,
            "hit_rate": np.nan,
            "officer_fte_2025": values["officers_fte"],
            "final_target_fte": int(round(values["officers_fte"])),
            "delta_fte": 0,
            "core_grant_2025": values["core_grant"],
            "proposed_core_grant_2026": values["core_grant"],
            "core_grant_change": 0,
            "core_grant_change_pct": 0,
            "allocation_note": "Baseline retained because modelled crime demand was unavailable.",
        })

    df_alloc["allocation_note"] = "Modelled allocation target."

    if fallback_rows:
        print(
            "Forces without modelled demand kept at baseline: "
            f"{[row['police_force'] for row in fallback_rows]}"
        )

        df_alloc = pd.concat(
            [df_alloc, pd.DataFrame(fallback_rows)],
            ignore_index=True
        )

    return df_alloc


def main():
    print("=== 1. BUILDING FORCE-YEAR DEMAND DATASET ===")

    df_lsoa = pd.read_parquet(
        STREET_PATH,
        columns=["lsoa_code", "reported_by"]
    ).dropna()

    # Assign each LSOA to the police force most commonly recorded there.
    lsoa_force_map = (
        df_lsoa
        .groupby("lsoa_code")["reported_by"]
        .agg(lambda x: x.value_counts().index[0])
        .to_dict()
    )

    # Average deprivation scores to police-force level.
    df_deprivation_raw = pd.read_excel(
        DEPRIVATION_PATH,
        sheet_name="IoD2019 Scores"
    )

    column_mapping = {
        "LSOA code (2011)": "lsoa_code",
        "Income Score (rate)": "income_score",
        "Education, Skills and Training Score": "education_score",
        "Health Deprivation and Disability Score": "health_score",
        "Barriers to Housing and Services Score": "housing_score",
    }

    for column in column_mapping:
        if column not in df_deprivation_raw.columns:
            raise KeyError(
                f"Expected column '{column}' not found in the deprivation dataset."
            )

    df_deprivation_raw = df_deprivation_raw.rename(columns=column_mapping)

    df_deprivation_raw["street_force"] = (
        df_deprivation_raw["lsoa_code"].map(lsoa_force_map)
    )
    df_deprivation_raw["police_force"] = (
        df_deprivation_raw["street_force"].map(FORCE_NAME_MAPPING)
    )

    df_deprivation = (
        df_deprivation_raw
        .dropna(subset=["police_force"])
        .groupby("police_force")[
            [
                "income_score",
                "education_score",
                "health_score",
                "housing_score",
            ]
        ]
        .mean()
        .reset_index()
    )

    df_coords = pd.read_parquet(
        STREET_PATH,
        columns=["reported_by", "latitude", "longitude"]
    ).dropna()

    df_coords["police_force"] = df_coords["reported_by"].map(FORCE_NAME_MAPPING)

    # Approximate each force's location using average crime coordinates.
    df_force_coords = (
        df_coords
        .dropna(subset=["police_force"])
        .groupby("police_force")[["latitude", "longitude"]]
        .mean()
        .reset_index()
    )

    df_street = pd.read_parquet(
        STREET_PATH,
        columns=["reported_by", "month", "crime_type"]
    ).dropna()

    df_street["year"] = df_street["month"].astype(str).str[:4].astype(int)
    df_street = df_street[df_street["year"].between(2021, 2025)]

    # Convert crime counts into harm-weighted yearly CHI totals.
    counts = (
        df_street
        .groupby(["reported_by", "year", "crime_type"])
        .size()
        .reset_index(name="count")
    )

    counts["police_force"] = counts["reported_by"].map(FORCE_NAME_MAPPING)
    counts["median_score"] = counts["crime_type"].map(CCHI_MEDIAN_SCORES)

    counts = counts.dropna(subset=["police_force", "median_score"])
    counts["total_chi"] = counts["count"] * counts["median_score"]

    df_chi_year = (
        counts
        .groupby(["police_force", "year"])["total_chi"]
        .sum()
        .reset_index()
    )

    df_panel = pd.merge(df_chi_year, df_deprivation, on="police_force")
    df_panel = pd.merge(df_panel, df_force_coords, on="police_force")

    if df_panel.empty:
        raise ValueError("The force-year panel dataset is empty after merging.")

    print(f"Panel dataset contains {len(df_panel)} force-year observations.")

    print("\n=== 2. CALCULATING YEARLY SPATIAL LAG ===")

    df_panel = pd.concat(
        [
            add_spatial_lag_for_year(year_df).assign(year=year)
            for year, year_df in df_panel.groupby("year")
        ],
        ignore_index=True
    )

    print("\n=== 3. CREATING 2026 FORECASTING DATA ===")

    df_panel = df_panel.sort_values(["police_force", "year"])

    df_panel["previous_year_chi"] = (
        df_panel.groupby("police_force")["total_chi"].shift(1)
    )

    df_panel["spatial_lag_chi_lag1"] = (
        df_panel.groupby("police_force")["spatial_lag_chi"].shift(1)
    )

    df_model = df_panel.dropna(
        subset=["previous_year_chi", "spatial_lag_chi_lag1"]
    ).copy()

    features = [
        "income_score",
        "education_score",
        "health_score",
        "housing_score",
        "previous_year_chi",
        "spatial_lag_chi_lag1",
    ]

    rf = RandomForestRegressor(
        n_estimators=500,
        max_depth=6,
        random_state=42,
        n_jobs=-1
    )

    rf.fit(df_model[features].values, df_model["total_chi"].values)

    df_2025 = df_panel[df_panel["year"] == 2025].copy()

    if df_2025.empty:
        raise ValueError("No 2025 data available for creating the 2026 forecast.")

    # Lag the 2025 values so they can be used as predictors for 2026.
    df_2026 = df_2025[
        [
            "police_force",
            "income_score",
            "education_score",
            "health_score",
            "housing_score",
            "total_chi",
            "spatial_lag_chi",
            "latitude",
            "longitude",
        ]
    ].copy()

    df_2026 = df_2026.rename(columns={
        "total_chi": "previous_year_chi",
        "spatial_lag_chi": "spatial_lag_chi_lag1",
    })

    df_2026["predicted_chi_2026"] = rf.predict(df_2026[features].values)

    print("\n=== 4. CALCULATING STOP-AND-SEARCH HIT RATES ===")

    df_lsoa_coords = (
        pd.read_parquet(
            STREET_PATH,
            columns=["lsoa_code", "latitude", "longitude"]
        )
        .dropna()
        .groupby("lsoa_code")[["latitude", "longitude"]]
        .mean()
        .reset_index()
    )

    if df_lsoa_coords.empty:
        raise ValueError("No valid LSOA coordinates found for stop-search matching.")

    df_ss = pd.read_parquet(
        STOP_SEARCH_PATH,
        columns=[
            "latitude",
            "longitude",
            "outcome",
            "outcome_linked_to_object_of_search",
        ]
    ).dropna(subset=["latitude", "longitude"])

    if df_ss.empty:
        raise ValueError("No stop-and-search records with valid coordinates found.")

    # Stop-and-search records do not include LSOA codes. Assign each record to the nearest approximate LSOA centroid.
    tree = cKDTree(df_lsoa_coords[["latitude", "longitude"]].values)
    _, indices = tree.query(df_ss[["latitude", "longitude"]].values)

    df_ss["lsoa_code"] = df_lsoa_coords.iloc[indices]["lsoa_code"].values
    df_ss["street_force"] = df_ss["lsoa_code"].map(lsoa_force_map)
    df_ss["police_force"] = df_ss["street_force"].map(FORCE_NAME_MAPPING)

    df_ss_clean = df_ss.dropna(subset=["police_force"]).copy()

    if df_ss_clean.empty:
        raise ValueError("No stop-and-search records could be mapped to forces.")

    df_ss_clean["success"] = df_ss_clean.apply(is_success, axis=1)

    df_success = (
        df_ss_clean
        .groupby("police_force")["success"]
        .agg(success_count="sum", search_count="count")
        .reset_index()
    )

    df_success["hit_rate"] = (
        df_success["success_count"] / df_success["search_count"]
    )

    national_avg_hit_rate = df_ss_clean["success"].mean()

    print("\n=== 5. BUILDING REALLOCATION DATASET ===")

    df_funding = pd.DataFrame([
        {
            "police_force": force,
            "officer_fte_2025": values["officers_fte"],
            "core_grant_2025": values["core_grant"],
        }
        for force, values in POLICE_FORCE_FUNDING.items()
    ])

    df_alloc = pd.merge(
        df_2026,
        df_success[["police_force", "hit_rate"]],
        on="police_force",
        how="inner"
    )

    df_alloc = pd.merge(
        df_alloc,
        df_funding,
        on="police_force",
        how="inner"
    )

    if df_alloc.empty:
        raise ValueError("The allocation dataset is empty after merging.")

    H_total_modelled = int(round(df_alloc["officer_fte_2025"].sum()))

    # Allocate officers in proportion to forecast 2026 CHI demand.
    df_alloc["baseline_target"] = (
        H_total_modelled
        * df_alloc["predicted_chi_2026"]
        / df_alloc["predicted_chi_2026"].sum()
    )

    # Adjust allocations using relative stop-and-search hit rates while
    # limiting the influence of operational efficiency differences.
    df_alloc["efficiency_multiplier"] = (
        df_alloc["hit_rate"] / national_avg_hit_rate
    ).clip(0.75, 1.25)

    df_alloc["adjusted_target"] = (
        df_alloc["baseline_target"] * df_alloc["efficiency_multiplier"]
    )

    # Rescale targets so the total allocated officer pool remains unchanged.
    df_alloc["scaled_target"] = (
        df_alloc["adjusted_target"]
        * (H_total_modelled / df_alloc["adjusted_target"].sum())
    )

    # Convert fractional targets to whole officers.
    df_alloc["floor_target"] = np.floor(df_alloc["scaled_target"]).astype(int)

    residual_officers = H_total_modelled - df_alloc["floor_target"].sum()

    df_alloc["fractional_remainder"] = (
        df_alloc["scaled_target"] - df_alloc["floor_target"]
    )

    df_alloc = df_alloc.sort_values(
        by="fractional_remainder",
        ascending=False
    ).reset_index(drop=True)

    df_alloc["final_target_fte"] = df_alloc["floor_target"]

    # Distribute remaining officers to the forces with the largest
    # fractional remainders.
    df_alloc.loc[
        df_alloc.index[:residual_officers],
        "final_target_fte"
    ] += 1

    assert df_alloc["final_target_fte"].sum() == H_total_modelled

    df_alloc["delta_fte"] = (
        df_alloc["final_target_fte"] - df_alloc["officer_fte_2025"]
    )

    # Create an illustrative harm-weighted core grant scenario.
    total_core_grant_modelled = df_alloc["core_grant_2025"].sum()

    df_alloc["proposed_core_grant_2026"] = (
        total_core_grant_modelled
        * df_alloc["predicted_chi_2026"]
        / df_alloc["predicted_chi_2026"].sum()
    )

    df_alloc["core_grant_change"] = (
        df_alloc["proposed_core_grant_2026"] - df_alloc["core_grant_2025"]
    )

    df_alloc["core_grant_change_pct"] = (
        df_alloc["core_grant_change"] / df_alloc["core_grant_2025"] * 100
    )

    df_alloc = add_baseline_only_forces(df_alloc)

    allocation_output_columns = [
        "police_force",
        "predicted_chi_2026",
        "hit_rate",
        "officer_fte_2025",
        "final_target_fte",
        "delta_fte",
        "core_grant_2025",
        "proposed_core_grant_2026",
        "core_grant_change",
        "core_grant_change_pct",
        "allocation_note",
    ]

    df_alloc[allocation_output_columns].to_csv(
        ALLOCATION_TARGETS_PATH,
        index=False
    )

    print(f"Allocation targets saved to {ALLOCATION_TARGETS_PATH}")

    print("\n=== 6. SOLVING SPATIAL REALLOCATION LP ===")

    modelled_alloc = df_alloc[
        df_alloc["allocation_note"] == "Modelled allocation target."
    ]

    surplus_df = modelled_alloc[modelled_alloc["delta_fte"] < 0].copy()
    deficit_df = modelled_alloc[modelled_alloc["delta_fte"] > 0].copy()

    surplus_df["supply"] = surplus_df["delta_fte"].abs().astype(int)
    deficit_df["demand"] = deficit_df["delta_fte"].astype(int)

    num_origins = len(surplus_df)
    num_destinations = len(deficit_df)

    transfers = []

    if num_origins > 0 and num_destinations > 0:
        cost_matrix = np.zeros((num_origins, num_destinations))

        for i in range(num_origins):
            for j in range(num_destinations):
                cost_matrix[i, j] = haversine_distance(
                    surplus_df.iloc[i]["latitude"],
                    surplus_df.iloc[i]["longitude"],
                    deficit_df.iloc[j]["latitude"],
                    deficit_df.iloc[j]["longitude"],
                )

        c = cost_matrix.flatten()

        A_eq = []
        b_eq = []

        for i in range(num_origins):
            row = np.zeros((num_origins, num_destinations))
            row[i, :] = 1
            A_eq.append(row.flatten())
            b_eq.append(surplus_df.iloc[i]["supply"])

        for j in range(num_destinations):
            row = np.zeros((num_origins, num_destinations))
            row[:, j] = 1
            A_eq.append(row.flatten())
            b_eq.append(deficit_df.iloc[j]["demand"])

        # Solve for the lowest-distance set of officer transfers.
        res = linprog(
            c,
            A_eq=np.array(A_eq),
            b_eq=np.array(b_eq),
            bounds=(0, None),
            method="highs"
        )

        if not res.success:
            raise RuntimeError(f"Linear programming failed: {res.message}")

        x_opt = res.x.reshape(num_origins, num_destinations)

        for i in range(num_origins):
            for j in range(num_destinations):
                flow = round(x_opt[i, j])

                if flow > 0:
                    distance = cost_matrix[i, j]

                    transfers.append({
                        "Origin": surplus_df.iloc[i]["police_force"],
                        "Destination": deficit_df.iloc[j]["police_force"],
                        "FTE shifted": flow,
                        "Haversine distance miles": distance,
                        "Total officer-miles": flow * distance,
                    })

    if transfers:
        df_transfers = (
            pd.DataFrame(transfers)
            .sort_values(by="Total officer-miles", ascending=False)
        )
    else:
        df_transfers = pd.DataFrame(columns=[
            "Origin",
            "Destination",
            "FTE shifted",
            "Haversine distance miles",
            "Total officer-miles",
        ])

    df_transfers.to_csv(TRANSFERS_PATH, index=False)

    print("\n=== 7. WRITING REALLOCATION AUDIT REPORT ===")

    total_shifted = df_transfers["FTE shifted"].sum()
    total_officer_miles = df_transfers["Total officer-miles"].sum()

    average_transfer_distance = (
        total_officer_miles / total_shifted
        if total_shifted > 0
        else 0
    )

    total_officer_pool = int(round(df_alloc["officer_fte_2025"].sum()))
    total_core_grant_pool = df_alloc["core_grant_2025"].sum()

    baseline_only_forces = df_alloc[
        df_alloc["allocation_note"] != "Modelled allocation target."
    ]["police_force"].tolist()

    top_10 = df_transfers.head(10)

    report_content = f"""# 2026 Police Resource Reallocation Audit

## 1. Allocation Summary

| Quantity | Value |
| :--- | ---: |
| Total officer FTE pool | {total_officer_pool:,} |
| Total FTE reallocated | {int(total_shifted):,} |
| Reallocation rate | {total_shifted / total_officer_pool * 100:.2f}% |
| Total core grant pool | £{total_core_grant_pool:,.0f} |
| Total officer-miles | {total_officer_miles:,.2f} |
| Average transfer distance | {average_transfer_distance:.2f} miles |

## 2. Baseline-Only Forces

{", ".join(baseline_only_forces) if baseline_only_forces else "None"}

## 3. Top 10 Recommended Transfers

| Origin | Destination | FTE shifted | Distance miles | Officer-miles |
| :--- | :--- | ---: | ---: | ---: |
"""

    if top_10.empty:
        report_content += "| No transfers required | No transfers required | 0 | 0.00 | 0.00 |\n"
    else:
        for _, row in top_10.iterrows():
            report_content += (
                f"| {row['Origin']} | {row['Destination']} | "
                f"{int(row['FTE shifted'])} | "
                f"{row['Haversine distance miles']:.2f} | "
                f"{row['Total officer-miles']:.2f} |\n"
            )

    report_content += """
## 4. Interpretation

This output should be interpreted as a decision-support scenario rather than a direct operational instruction.

The 2026 CHI values are forecasts produced from historical crime, deprivation, spatial lag and previous-year CHI features. The allocation results therefore depend on model assumptions and should be treated as scenario analysis rather than predictions of future resource requirements.

The officer pool is fixed, so increases in some forces require decreases elsewhere. The transfer table shows the lowest-distance way to satisfy the modelled increases and decreases among forces with available modelled demand.

The core grant figures are included as an illustrative harm-weighted funding scenario. They should not be interpreted as a real funding recommendation, because police funding includes other grants, local precept income, pensions, capital costs, and political constraints.

Forces without modelled demand were kept at their 2025 baseline officer FTE and core grant.
"""

    with open(AUDIT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Optimized transfers saved to {TRANSFERS_PATH}")
    print(f"Reallocation audit saved to {AUDIT_PATH}")


if __name__ == "__main__":
    main()