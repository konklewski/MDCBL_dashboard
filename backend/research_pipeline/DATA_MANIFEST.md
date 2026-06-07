# Backend Data Manifest

## Present In Backend

- `Crime severity scores.docx`: CCHI category median source.
- `Police force in England.xlsx`: baseline headcount and core grant source.
- `data/File_5_IoD2019_Scores.xlsx`: IMD 2019 LSOA score source.
- `data/street_from_2018.parquet`: street crime source used for LSOA-force mapping and historical operations.
- `data/street_from_2021.parquet`: street crime source used for 2025 CHI computation.
- `data/stop_and_search_from_2021.parquet`: stop-and-search source used for hit-rate computation.
- `data/stop_and_searchfrom_2018.parquet`: legacy stop-and-search source retained from research folder.
- `data/outcomes_from_2018.parquet`: legacy outcomes source retained from research folder.
- `data/outcomes_from_2021.parquet`: legacy outcomes source retained from research folder.
- `legacy_scripts/*.py`: original research scripts copied for auditability.
- `pipeline.py`: consolidated backend recomputation pipeline.
- `cache/research_snapshot.json`: current API cache.

## Current Cache Correctness

Current cache mode: `from-existing`.

Correct in current cache:

- CCHI median parsing from `Crime severity scores.docx`.
- baseline FTE and core grant from `Police force in England.xlsx`.
- optimized transfer legs from `report/optimized_officer_transfers.csv`.
- national reallocation summary from `feedback/reallocation_optimization_audit.md`.
- unsupported-force scope flags.

Not present in current cache until full recompute:

- per-force observed CHI.
- per-force Random Forest predicted CHI.
- per-force spatial lag CHI.
- per-force stop-and-search hit rate.
- per-force IMD aggregate values.
- per-force centroid coordinates.
- per-force crime category counts.
- top high-demand LSOAs.

## Not Implemented Because Data/Model Missing

- Internal LSOA officer deployment.
- Lloyd/k-means station allocation.
- station capacity constraints.
- response-time objective.
- LSOA-level final officer targets.

The old UI animation for Lloyd was a placeholder and has been removed.

## Known Research Inconsistency

`feedback/reallocation_optimization_audit.md` says Random Forest predicted CHI feeds allocation.

`legacy_scripts/run_reallocation.py` computes allocation using observed `total_chi` from 2025 street incidents.

Backend preserves this distinction. No predicted-CHI allocation is claimed unless full recompute is changed and rerun with that explicit basis.
