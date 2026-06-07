# Research Backend Pipeline

This backend owns the research inputs and recomputation logic used by the app.

## Data Ownership

Large parquet files in `data/` are hard links to the original research files. They do not duplicate 10GB on disk. If the old `Multidisciplinary CBL/Multidisciplinary-CBL-2026-Group-30` folder is deleted, these backend paths still keep the data as long as the backend hard links remain.

## Commands

Create a cache from already-generated research reports:

```bash
python3 backend/research_pipeline/pipeline.py --mode from-existing
```

Run full recomputation from raw parquet/docx/xlsx:

```bash
python3 -m pip install -r backend/research_pipeline/requirements.txt
python3 backend/research_pipeline/pipeline.py --mode full
```

## Current Truth Boundary

`from-existing` mode uses verified existing outputs: `report/optimized_officer_transfers.csv`, audit markdown, `Crime severity scores.docx`, and `Police force in England.xlsx`.

`full` mode contains the complete computations for:

- CCHI median parsing from Word document
- LSOA to force mapping from street crime parquet
- IMD aggregation from IoD 2019 spreadsheet
- 2025 CHI aggregation from street crime parquet
- KNN spatial lag feature
- Random Forest fit and validation
- Stop-and-search hit-rate computation
- Hamilton apportionment target allocation
- Haversine transportation LP via `scipy.optimize.linprog`
- VIF diagnostics via least-squares auxiliary regressions

Not implemented: internal LSOA deployment / Lloyd allocation. No LSOA-level officer placement targets or constraints exist in the research files, so backend exposes this as missing rather than faking it.
