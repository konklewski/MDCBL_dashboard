import os
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from crime_severity_scores import CCHI_MEDIAN_SCORES
from force_name_mapping import FORCE_NAME_MAPPING


os.makedirs("report", exist_ok=True)
os.makedirs("feedback", exist_ok=True)

CRIME_FILE = "data/street_from_2021.parquet"
ALLOCATION_TARGET_FILE = "report/reallocation_targets_2026.csv"

OUTPUT_FILE = "report/lsoa_harm_surface.csv"
REPORT_FILE = "feedback/lsoa_harm_surface_report.md"

N_NEIGHBOURS = 6
LOCAL_WEIGHT = 0.75
NEIGHBOUR_WEIGHT = 0.25


def minmax(series):
    """Scale values from 0 to 1 within each police force."""

    if series.max() == series.min():
        return pd.Series(0, index=series.index)

    return (series - series.min()) / (series.max() - series.min())


def allocate_lsoa_officers(group):
    """Redistribute one police force's assigned officers across its LSOAs."""

    group = group.copy()

    total_officers = int(round(group["assigned_force_officers"].iloc[0]))

    group["suggested_lsoa_officers_raw"] = (
        group["lsoa_share_of_force_demand"] * total_officers
    )

    group["suggested_lsoa_officers"] = (
        group["suggested_lsoa_officers_raw"]
        .round()
        .astype(int)
    )

    difference = total_officers - group["suggested_lsoa_officers"].sum()

    # Rounding can make the LSOA total slightly too high or too low.
    # Adjust the highest-demand or lowest-demand LSOAs until the force total matches.
    if difference > 0:
        order = group["spatial_demand_score"].sort_values(ascending=False).index

        for idx in order[:difference]:
            group.loc[idx, "suggested_lsoa_officers"] += 1

    elif difference < 0:
        order = group["spatial_demand_score"].sort_values(ascending=True).index

        for idx in order:
            if difference == 0:
                break

            if group.loc[idx, "suggested_lsoa_officers"] > 0:
                group.loc[idx, "suggested_lsoa_officers"] -= 1
                difference += 1

    return group


def main():
    print("=== 1. LOADING STREET CRIME DATA ===")

    df = pd.read_parquet(
        CRIME_FILE,
        columns=[
            "month",
            "reported_by",
            "lsoa_code",
            "lsoa_name",
            "crime_type",
            "latitude",
            "longitude",
        ],
    )

    df = df.dropna(
        subset=[
            "month",
            "reported_by",
            "lsoa_code",
            "crime_type",
            "latitude",
            "longitude",
        ]
    )

    df["month"] = pd.to_datetime(df["month"])
    start_month = df["month"].min().strftime("%Y-%m")
    end_month = df["month"].max().strftime("%Y-%m")

    df["police_force"] = df["reported_by"].map(FORCE_NAME_MAPPING)
    df = df.dropna(subset=["police_force"])

    print(f"Crime data period: {start_month} to {end_month}")
    print(f"Usable crime records: {len(df):,}")

    print("\n=== 2. CALCULATING LSOA-LEVEL CRIME HARM ===")

    # Map each crime type to its harm score.
    df["crime_harm"] = df["crime_type"].map(CCHI_MEDIAN_SCORES).fillna(1)

    lsoa = (
        df.groupby(["police_force", "lsoa_code", "lsoa_name"], as_index=False)
        .agg(
            crime_count=("crime_type", "count"),
            crime_harm=("crime_harm", "sum"),
            latitude=("latitude", "mean"),
            longitude=("longitude", "mean"),
            first_month=("month", "min"),
            last_month=("month", "max"),
        )
    )

    print(f"LSOAs in harm surface: {len(lsoa):,}")

    print("\n=== 3. ADDING FORCE-LEVEL OFFICER ALLOCATIONS ===")

    targets = pd.read_csv(ALLOCATION_TARGET_FILE)

    # Check that the allocation file has the columns needed for LSOA redistribution.
    required_columns = [
        "police_force",
        "officer_fte_2025",
        "final_target_fte",
        "delta_fte",
    ]

    for column in required_columns:
        if column not in targets.columns:
            raise KeyError(
                f"Expected column '{column}' not found in {ALLOCATION_TARGET_FILE}."
            )

    force_alloc = targets[required_columns].copy()

    force_alloc = force_alloc.rename(columns={
        "officer_fte_2025": "baseline_force_officers",
        "final_target_fte": "assigned_force_officers",
        "delta_fte": "force_officer_delta",
    })

    lsoa = lsoa.merge(force_alloc, on="police_force", how="left")

    if lsoa["assigned_force_officers"].isna().any():
        missing_forces = lsoa.loc[
            lsoa["assigned_force_officers"].isna(),
            "police_force"
        ].unique()

        raise ValueError(
            "Some police forces do not have assigned officer totals: "
            f"{missing_forces}"
        )

    print("\n=== 4. SCALING LOCAL HARM WITHIN EACH FORCE ===")

    # Scale harm scores within each force so LSOAs are compared locally.
    lsoa["harm_risk_scaled"] = (
        lsoa.groupby("police_force")["crime_harm"].transform(minmax)
    )

    print("\n=== 5. CALCULATING NEIGHBOURING HARM RISK ===")

    lsoa["neighbour_harm_risk"] = 0.0

    # Find nearby LSOAs within the same police force.
    for force, group in lsoa.groupby("police_force"):
        idx = group.index.to_numpy()

        if len(group) <= 1:
            lsoa.loc[idx, "neighbour_harm_risk"] = 0.0
            continue

        k = min(N_NEIGHBOURS + 1, len(group))

        coords = group[["latitude", "longitude"]].to_numpy()
        local_risk = group["harm_risk_scaled"].to_numpy()

        nn = NearestNeighbors(n_neighbors=k)
        nn.fit(coords)

        _, neighbours = nn.kneighbors(coords)

        neighbour_scores = []

        for row in neighbours:
            neighbour_ids = row[1:]
            neighbour_scores.append(local_risk[neighbour_ids].mean())

        lsoa.loc[idx, "neighbour_harm_risk"] = neighbour_scores

    print("\n=== 6. BUILDING FINAL SPATIAL DEMAND SCORE ===")

    # Combine local harm and neighbouring harm into one demand score.
    lsoa["spatial_demand_score"] = (
        LOCAL_WEIGHT * lsoa["harm_risk_scaled"]
        + NEIGHBOUR_WEIGHT * lsoa["neighbour_harm_risk"]
    )

    lsoa["spatial_demand_score"] = lsoa["spatial_demand_score"].clip(
        lower=0.0001
    )

    lsoa["lsoa_share_of_force_demand"] = (
        lsoa["spatial_demand_score"]
        / lsoa.groupby("police_force")["spatial_demand_score"].transform("sum")
    )

    lsoa["lsoa_share_of_national_demand"] = (
        lsoa["spatial_demand_score"]
        / lsoa["spatial_demand_score"].sum()
    )

    print("\n=== 7. REDISTRIBUTING ASSIGNED OFFICERS ACROSS LSOAS ===")

    allocated_groups = []

    for police_force, group in lsoa.groupby("police_force"):
        group = group.copy()
        group["police_force"] = police_force
        allocated_groups.append(allocate_lsoa_officers(group))

    lsoa = pd.concat(allocated_groups, ignore_index=True)

    check = (
        lsoa.groupby("police_force")
        .agg(
            assigned_force_officers=("assigned_force_officers", "first"),
            suggested_lsoa_total=("suggested_lsoa_officers", "sum"),
        )
        .reset_index()
    )

    check["difference"] = (
        check["assigned_force_officers"] - check["suggested_lsoa_total"]
    )

    if (check["difference"] != 0).any():
        print("Warning: some force totals do not match their LSOA totals.")
        print(check[check["difference"] != 0].to_string(index=False))
    else:
        print("All force totals match their suggested LSOA officer totals.")

    lsoa = lsoa.sort_values(
        ["police_force", "suggested_lsoa_officers", "spatial_demand_score"],
        ascending=[True, False, False],
    )

    output_columns = [
        "police_force",
        "baseline_force_officers",
        "assigned_force_officers",
        "force_officer_delta",
        "lsoa_code",
        "lsoa_name",
        "latitude",
        "longitude",
        "crime_count",
        "crime_harm",
        "harm_risk_scaled",
        "neighbour_harm_risk",
        "spatial_demand_score",
        "lsoa_share_of_force_demand",
        "lsoa_share_of_national_demand",
        "suggested_lsoa_officers_raw",
        "suggested_lsoa_officers",
        "first_month",
        "last_month",
    ]

    lsoa[output_columns].to_csv(OUTPUT_FILE, index=False)

    print(f"Saved LSOA harm surface to {OUTPUT_FILE}")

    print("\n=== 8. WRITING METHODOLOGY REPORT ===")

    report_content = f"""# LSOA Harm Surface Report

## 1. Rationale

This script creates a descriptive LSOA-level harm surface rather than a second forecasting model.

An LSOA-level forecasting model was considered, but validation showed that previous-year CHI performed better than the Random Forest model. Therefore, the final approach uses observed harm over the available period with local spatial smoothing.

The purpose of this output is to translate the force-level 2026 officer allocation into a more detailed LSOA-level demand surface.

## 2. Methodology

Police.uk crime records were aggregated to LSOA level. Each crime type was mapped to a CCHI median severity score, and the scores were summed to produce total observed harm for each LSOA.

The local harm score was scaled from 0 to 1 within each police force. A neighbouring harm score was then calculated using nearby LSOAs from the same police force.

The final spatial demand score was calculated as:

`0.75 × local harm risk + 0.25 × neighbouring harm risk`

Each police force's assigned officers were redistributed across its LSOAs in proportion to the LSOA share of that force's spatial demand score. Rounding differences were corrected within each force so that the LSOA totals match the assigned force-level officer total.

## 3. Limitations

This is not a predictive model. It is a harm-weighted spatial demand surface based on observed crime records.

The LSOA-level officer numbers are proportional suggestions based on the spatial demand score. They should not be interpreted as direct operational staffing recommendations.

The neighbour calculation uses average recorded crime coordinates as approximate LSOA centroids. Official LSOA boundary centroids would be preferable if exact geographic adjacency were required.
"""

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"Saved methodology report to {REPORT_FILE}")


if __name__ == "__main__":
    main()