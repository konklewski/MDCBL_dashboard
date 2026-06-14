# Research Pipeline

The data pipeline behind Force Flow. It turns raw crime, stop-and-search,
deprivation and funding data into the optimised officer allocation, the
inter-force transfer flows and the per-force facts that the dashboard reads.

The frontend ships with the generated files committed, so this pipeline only
needs to run when the underlying data or model changes.

## Requirements

Python 3.10 or newer (developed on 3.13).

```bash
python3 -m pip install -r requirements.txt
```

Core libraries: pandas, numpy, scikit-learn, scipy, geopandas, openpyxl,
python-docx, pyarrow.

## Inputs

| File | Used for |
| --- | --- |
| `data/street_from_2021.parquet` | 2021–2025 street crime; CHI forecast features, 2025 crime counts |
| `data/street_from_2018.parquet` | 2018+ street crime; LSOA→force mapping in the full recompute path |
| `data/stop_and_search_from_2021.parquet` | stop-and-search hit-rate efficiency multipliers |
| `data/File_5_IoD2019_Scores.xlsx` | IoD 2019 LSOA deprivation scores |
| `Crime severity scores.docx` | Cambridge Crime Harm Index category weights |
| `Police force in England.xlsx` | baseline force headcount and core grant funding |

## Regenerating the dashboard data

The dashboard consumes four generated artefacts. Run these in order from the
repository root.

1. **`forecast_and_reallocate_2026.py`** — fits the 2026 Random Forest CHI
   forecast on the 2021–2025 force-year panel, applies stop-and-search
   efficiency multipliers and Hamilton apportionment, then solves the
   Haversine officer-transfer LP. Writes `report/reallocation_targets_2026.csv`
   and `report/optimized_officer_transfers_2026.csv`.

2. **`build_lsoa_harm_surface.py`** — distributes each force's demand down to
   LSOA level to produce `report/lsoa_harm_surface.csv`, the demand surface used
   by the internal-allocation step.

3. **`pipeline.py --mode from-existing`** — assembles the forecast targets and
   transfer legs into `cache/research_snapshot.json`, the snapshot that feeds
   `src/data/researchSnapshot.generated.ts`.

4. **`scripts/generate_force_facts.py`** — computes per-force land area and 2025
   recorded-crime counts, writing `src/data/forceFacts.generated.ts`.

`internal_allocation/` produces the per-force LSOA officer placements and
animations (see its own README), writing `report/sortedLsoaOfficerAllocation.csv`
and the GIFs in `public/animations/`. `scripts/generate_lloyd_allocation.py` then
summarises that CSV into `src/data/lloydAllocation.generated.ts` for the Policy tab.

`pipeline.py --mode full` is the legacy single-pass recompute that rebuilds the
snapshot from the raw parquet/docx/xlsx inputs directly. The `from-existing`
mode above is the supported path.

## Layout

```
pipeline.py                    snapshot assembler (from-existing | full)
forecast_and_reallocate_2026.py  Random Forest forecast + LP reallocation
build_lsoa_harm_surface.py     per-LSOA demand surface
crime_severity_scores.py       Crime Harm Index category weights
force_name_mapping.py          force-name normalisation
police_force_funding.py        baseline headcount + core grant
scripts/generate_force_facts.py      per-force area + 2025 crime counts
scripts/generate_lloyd_allocation.py LSOA officer-allocation summary
internal_allocation/           within-force LSOA officer placement
data/                          raw inputs (parquet / xlsx)
report/                        intermediate + final CSV outputs
cache/research_snapshot.json   assembled API snapshot
```

## Scope notes

- London is modelled as a single merged force; the City of London is kept
  separate from the Metropolitan Police.
- The internal-allocation step runs on the 39 territorial forces with usable
  LSOA geometry, including the Metropolitan Police and City of London.
- Greater Manchester has no 2025 street-crime rows in the open police.uk feed
  (GMP withdrew from it), so its recorded-crime counts are absent by source,
  not by error.
