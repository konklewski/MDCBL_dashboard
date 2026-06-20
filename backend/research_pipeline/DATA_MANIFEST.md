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

## Obtaining the raw inputs

The large raw inputs are **not committed** (they are git-ignored — see the root
`.gitignore`: `*.parquet`, `*.xlsx` under `data/`). They are public and free to
download. The pipeline's committed `report/*.csv` and `cache/research_snapshot.json`
let you reproduce the snapshot and the dashboard **without** re-downloading these;
you only need them for the `full` recompute path. To collect them from scratch:

| Input | Source | How |
| --- | --- | --- |
| `data/street_from_2021.parquet`, `data/street_from_2018.parquet` | Police recorded street-level crime, data.police.uk | Custom download at <https://data.police.uk/data/> — select all forces and the date range (Jan 2018 / Jan 2021 to latest), download the "street" CSVs, concatenate and save as Parquet (`pandas.read_csv(...).to_parquet(...)`). Open Government Licence v3.0. |
| `data/stop_and_search_from_2021.parquet` | Police stop-and-search, data.police.uk | Same custom download, tick "stop and search"; concatenate the stop-and-search CSVs to Parquet. |
| `data/File_5_IoD2019_Scores.xlsx` | English Indices of Deprivation 2019, MHCLG (gov.uk) | <https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019> — "File 5: scores for the indices of deprivation". |
| `Crime severity scores.docx` | ONS Crime Severity Score weights (England & Wales) | <https://www.ons.gov.uk/peoplepopulationandcommunity/crimeandjustice/datasets/crimeseverityscoredatatool> — per-offence severity weights used as the Crime Harm Index. |
| `Police force in England.xlsx` | Home Office — Police workforce + police funding settlement | Headcount: <https://www.gov.uk/government/collections/police-workforce-england-and-wales>. Core grant: <https://www.gov.uk/government/collections/police-funding> (2025–26 final settlement). |

Column names the code expects: street files — `lsoa_code`, `reported_by`,
`latitude`, `longitude`, `month`, `crime_type`; stop-and-search — `latitude`,
`longitude`, `outcome`, `outcome_linked_to_object_of_search`. Keep the file names
above so the paths in `pipeline.py` resolve unchanged.

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
