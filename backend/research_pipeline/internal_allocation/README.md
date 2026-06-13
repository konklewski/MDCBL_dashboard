# Internal Allocation

Within-force officer placement. Given a force's officer count and its LSOA-level
demand surface, this step decides *where inside the force* officers should sit,
producing the per-force animations and the LSOA allocation summary the dashboard
shows in the Policy tab.

## Method

Officers are split into two groups:

- **Anchor officers** — placed on a hexagonal grid at spacing `r_coverage_m` so
  every point in the territory is within that radius of an officer. Fixed; they
  guarantee baseline coverage.
- **Free officers** — placed by risk-weighted Lloyd's iteration. Each officer
  moves to the demand-weighted centroid of its Voronoi cell, where demand is the
  LSOA spatial demand score raised to `risk_exponent`. This is coordinate
  descent on the expected crime-to-officer travel distance, so the objective is
  non-increasing each iteration.

All geometry is in British National Grid (EPSG:27700), so distances are metres.

## Files

- `simulation2_weighted.py` — runs the weighted-Lloyd's placement for the force
  in `config.json`. Writes officer positions and density samples.
- `compareStats.py` — builds hex-grid and RTM baselines, simulates crime
  dispatch (Negative Binomial arrivals) across all three placements, and emits
  the comparison map and response-distance CDF.
- `config.json` — run parameters (force, coverage radius, risk exponent,
  simulation settings, seed).
- `lsoaJoinedTerritory/` — dissolved LSOA territory shapefile for the force.

## Inputs

- `lsoaJoinedTerritory/lsoaJoinedTerritory.shp` — force territory geometry.
- `../report/lsoa_harm_surface.csv` — per-LSOA demand surface.

## Running

```bash
python3 simulation2_weighted.py
python3 compareStats.py
```

Set the target force and parameters in `config.json` first.
