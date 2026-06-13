# Data Manifest

What lives in this backend and what each artefact is for.

## Raw inputs (`data/` and root)

- `Crime severity scores.docx` — Cambridge Crime Harm Index category weights.
- `Police force in England.xlsx` — baseline force headcount and core grant.
- `data/File_5_IoD2019_Scores.xlsx` — IoD 2019 LSOA deprivation scores.
- `data/street_from_2021.parquet` — 2021–2025 street crime; forecast features
  and 2025 recorded-crime counts.
- `data/street_from_2018.parquet` — 2018+ street crime; LSOA→force mapping in
  the full recompute path.
- `data/stop_and_search_from_2021.parquet` — stop-and-search hit-rate inputs.

## Outputs (`report/`)

- `reallocation_targets_2026.csv` — per-force 2026 forecast CHI, hit rate,
  baseline FTE, proposed FTE and delta.
- `optimized_officer_transfers_2026.csv` — Haversine LP transfer legs for the
  2026 scenario.
- `optimized_officer_transfers.csv` — earlier transfer scenario, retained for
  reference.
- `lsoa_harm_surface.csv` — per-LSOA demand surface and suggested LSOA officer
  totals; input to the internal-allocation step.
- `sortedLsoaOfficerAllocation.csv` — internal LSOA officer allocation summary;
  source for `src/data/lloydAllocation.generated.ts`.

## Cache

- `cache/research_snapshot.json` — assembled snapshot consumed by
  `src/data/researchSnapshot.generated.ts`.

## What the snapshot carries

Per force: baseline FTE and core grant, predicted 2026 CHI, stop-and-search
hit rate, proposed FTE and transfer legs, and force-scope flags. Per-force
land area and 2025 crime-category counts are generated separately into
`src/data/forceFacts.generated.ts` by `scripts/generate_force_facts.py`.

## Modelling boundary

The 2026 cache uses `predicted_chi_2026` from `forecast_and_reallocate_2026.py`
as the demand signal driving reallocation — a yearly Random Forest forecast over
the 2021–2025 force-year panel using previous-year CHI, lagged spatial-neighbour
CHI and force-level deprivation features, followed by stop-and-search efficiency
multipliers, Hamilton apportionment and Haversine LP transport.

Internal within-force placement (LSOA officer positions) is produced by the
weighted-Lloyd's method in `internal_allocation/`, separate from the inter-force
LP above.
