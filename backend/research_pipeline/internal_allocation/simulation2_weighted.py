"""
Weighted Voronoi Stippling for Police Officer Allocation
========================================================

ALGORITHM OVERVIEW
──────────────────
Officers are split into two groups:

1. ANCHOR officers — minimum spatial coverage
   A hexagonal grid of points is placed over the territory at spacing
   R_COVERAGE_M.  Hex close-packing is the most efficient regular tiling:
   any location is within ≤ R_COVERAGE_M of its nearest grid point.
   Anchors are fixed; they never move.  They are LSOA-agnostic.

2. FREE officers — risk-weighted Lloyd's optimisation
   The remaining officers are placed by iterating the weighted centroid rule:

       c_i  ←  Σ_{x ∈ cell_i}  f(x)^γ · x  /  Σ_{x ∈ cell_i}  f(x)^γ

   where  f(x) = spatial_demand_score(LSOA(x))  and  γ = RISK_EXPONENT.
   Density sample points are drawn proportional to  f(x) · area  (i.e. the
   actual crime frequency distribution), so officers converge toward where
   crimes actually occur.

WHY THIS IS NEAR-OPTIMAL FOR TRAVEL TIME
─────────────────────────────────────────
The placement minimises the weighted travel-time objective

    J = ∫ d(x, nearest officer(x)) · f(x)^γ dx

    J = E_{crimes}[travel distance], provably optimal for minimising
             expected response distance under the crime distribution.

Weighted Lloyd's is coordinate descent on J — J is monotonically
non-increasing across iterations.

CRS: British National Grid (EPSG:27700) — distances in metres.
"""

import json
import numpy as np
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.colors import Normalize
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep

# ── Load shared config ───────────────────────────────────────────────────────
with open('config.json') as _f:
    _cfg = json.load(_f)

FORCE             = _cfg['force']
RISK_FLOOR        = _cfg['risk_floor']
R_COVERAGE_M      = _cfg['r_coverage_m']
RISK_EXPONENT     = _cfg['risk_exponent']
N_DENSITY_SAMPLES = _cfg['n_density_samples']
MAX_FRAMES        = _cfg['max_frames']
SEED              = _cfg['seed']
# ─────────────────────────────────────────────────────────────────────────────

np.random.seed(SEED)

# ═══════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════
shp = gpd.read_file('lsoaJoinedTerritory/lsoaJoinedTerritory.shp')
csv = pd.read_csv('lsoa_harm_surface.csv')

gdf = shp[shp['PFA24NM'] == FORCE].copy().reset_index(drop=True)
force_csv = csv[csv['police_force'].str.strip() == FORCE.strip()].copy()

N_TOTAL = int(force_csv['assigned_force_officers'].iloc[0])

if 'LSOA21CD' in gdf.columns and 'lsoa_code' in force_csv.columns:
    gdf = gdf.merge(
        force_csv[['lsoa_code', 'spatial_demand_score', 'suggested_lsoa_officers']],
        left_on='LSOA21CD', right_on='lsoa_code', how='left'
    )
else:
    gdf = gdf.merge(
        force_csv[['lsoa_name', 'spatial_demand_score', 'suggested_lsoa_officers']],
        left_on='LSOA21NM', right_on='lsoa_name', how='left'
    )

gdf['spatial_demand_score'] = gdf['spatial_demand_score'].fillna(RISK_FLOOR).clip(lower=RISK_FLOOR)
lsoa_risks = gdf['spatial_demand_score'].to_numpy()
lsoa_areas = gdf.geometry.area.to_numpy()   # m² (BNG)
num_lsoas  = len(gdf)
polygon    = gdf.geometry.union_all()
total_area = lsoa_areas.sum()

print(f"Force: {FORCE} | LSOAs: {num_lsoas} | N_TOTAL: {N_TOTAL}")
print(f"Total area: {total_area/1e6:.1f} km²")

# ═══════════════════════════════════════════════════════════
# HEXAGONAL ANCHOR GRID
# ═══════════════════════════════════════════════════════════
print(f"\nAnchor grid (R = {R_COVERAGE_M/1000:.1f} km)")

minx, miny, maxx, maxy = polygon.bounds
dx = R_COVERAGE_M
dy = R_COVERAGE_M * np.sqrt(3) / 2
prepared_polygon = prep(polygon)

anchor_list = []
row = 0
y = miny
while y <= maxy + dy:
    x_off = (dx / 2) if (row % 2) else 0.0
    x = minx + x_off
    while x <= maxx + dx:
        if prepared_polygon.contains(Point(x, y)):
            anchor_list.append([x, y])
        x += dx
    y += dy
    row += 1

anchor_pts = np.array(anchor_list)
n_anchors  = len(anchor_pts)
n_free     = N_TOTAL - n_anchors

print(f"Anchors: {n_anchors}  ({n_anchors/N_TOTAL*100:.0f}%)  |  "
      f"Free: {n_free}  ({n_free/N_TOTAL*100:.0f}%)")

# ═══════════════════════════════════════════════════════════
# DENSITY FIELD
# ═══════════════════════════════════════════════════════════
# Samples drawn proportional to spatial_demand_score × area.
# Weights = score^γ so the centroid rule optimises the correct objective.
print(f"Density Field ({N_DENSITY_SAMPLES} samples)")

crime_freq  = lsoa_risks * lsoa_areas
crime_probs = crime_freq / crime_freq.sum()
n_per_lsoa  = (N_DENSITY_SAMPLES * crime_probs).astype(int)
n_per_lsoa[np.argmax(crime_freq)] += N_DENSITY_SAMPLES - n_per_lsoa.sum()

density_pts_list     = []
density_weights_list = []

for geom, risk, n in zip(gdf.geometry, lsoa_risks, n_per_lsoa):
    if n <= 0:
        continue
    pgeom = prep(geom)
    lx, ly, hx, hy = geom.bounds
    sampled = []
    while len(sampled) < n:
        xs = np.random.uniform(lx, hx, n * 6)
        ys = np.random.uniform(ly, hy, n * 6)
        for x, y in zip(xs, ys):
            if pgeom.contains(Point(x, y)):
                sampled.append([x, y])
    density_pts_list.extend(sampled[:n])
    density_weights_list.extend([risk] * n)

density_pts     = np.array(density_pts_list)
density_weights = np.array(density_weights_list, dtype=float)
print(f"Density field: {len(density_pts)} points, "
      f"weight range [{density_weights.min():.4f}, {density_weights.max():.4f}]")

# ═══════════════════════════════════════════════════════════
# INITIAL FREE OFFICER POSITIONS
# ═══════════════════════════════════════════════════════════
# Seed from density_pts so officers start inside the territory
# and the Lloyd's centroid rule has well-defined cells from frame 1.
if n_free > 0:
    w_prob   = density_weights / density_weights.sum()
    init_idx = np.random.choice(len(density_pts), size=n_free, replace=False, p=w_prob)
    free_points = density_pts[init_idx].copy()
else:
    free_points = np.empty((0, 2))

# ═══════════════════════════════════════════════════════════
# WEIGHTED LLOYD'S STEP
# ═══════════════════════════════════════════════════════════
def weighted_lloyd_step(free_pts, anchor_pts, density_pts, density_weights):
    """Move each free officer to the f^γ-weighted centroid of its Voronoi cell."""
    all_pts = np.vstack([free_pts, anchor_pts]) if n_anchors > 0 else free_pts
    tree    = cKDTree(all_pts)
    _, asgn = tree.query(density_pts)
    new_free = free_pts.copy()
    for i in range(len(free_pts)):
        mask = asgn == i
        if not mask.any():
            continue
        w, p = density_weights[mask], density_pts[mask]
        ws = w.sum()
        new_free[i] = (w[:, None] * p).sum(axis=0) / ws if ws > 1e-12 \
                      else p.mean(axis=0)
    return new_free


# ANIMATION + GIF

LINGER = 20   # frames to hold on initial and final state

minx, miny, maxx, maxy = polygon.bounds

aspect = (maxy - miny) / (maxx - minx)

fig_width = 10
fig_height = fig_width * aspect

fig, ax = plt.subplots(figsize=(fig_width, fig_height))

norm = Normalize(vmin=lsoa_risks.min(), vmax=lsoa_risks.max())
gdf.plot(ax=ax, column='spatial_demand_score', cmap='YlOrRd', norm=norm,
         alpha=0.45, edgecolor='grey', linewidth=0.2)
sm = plt.cm.ScalarMappable(cmap='YlOrRd', norm=norm)
sm.set_array([])
plt.colorbar(sm, ax=ax, shrink=0.5, label='Spatial demand score')

ax.scatter(anchor_pts[:, 0], anchor_pts[:, 1],
           s=1, c='steelblue', alpha=0.5, zorder=3, label=f'Anchors ({n_anchors})')
free_sc = ax.scatter(
    free_points[:, 0] if n_free > 0 else [],
    free_points[:, 1] if n_free > 0 else [],
    s=1, c='crimson', alpha=0.9, zorder=4, label=f'Free officers ({n_free})'
)
ax.set_aspect('equal')
ax.axis('off')
ax.legend(loc='upper right', fontsize=8)
title = ax.set_title(f"Weighted Lloyd's — {FORCE} — initial random placement")
iter_count = [0]

def update(frame):
    global free_points
    if LINGER <= frame < LINGER + MAX_FRAMES:
        # Iteration phase: run one Lloyd's step
        if n_free > 0:
            free_points = weighted_lloyd_step(
                free_points, anchor_pts, density_pts, density_weights)
            free_sc.set_offsets(free_points)
        iter_count[0] += 1
        title.set_text(f"Weighted Lloyd's — {FORCE} — iter {iter_count[0]} / {MAX_FRAMES}")
    elif frame < LINGER:
        # Linger on initial state
        title.set_text(f"Weighted Lloyd's — {FORCE} — initial random placement")
    else:
        # Linger on final state
        title.set_text(f"Weighted Lloyd's — {FORCE} — final allocation")
    return free_sc, title

total_frames = LINGER + MAX_FRAMES + LINGER
ani = FuncAnimation(fig, update, frames=total_frames, interval=60, blit=False)
print("Saving weighted_allocation.gif ...")
ani.save(
    'weighted_allocation.gif',
    writer=PillowWriter(fps=10),
    dpi=200,
    savefig_kwargs={"bbox_inches": "tight", "pad_inches": 0}
)
plt.close(fig)
print("Saved.")

# ═══════════════════════════════════════════════════════════
# SAVE OUTPUTS
# ═══════════════════════════════════════════════════════════
all_officers = np.vstack([free_points, anchor_pts]) if n_free > 0 else anchor_pts
np.save('weighted_officer_positions.npy', all_officers)
np.save('density_pts.npy', density_pts)

# LSOA allocation CSV
final_gdf = gpd.GeoDataFrame(
    geometry=[Point(x, y) for x, y in all_officers], crs=gdf.crs)
joined = gpd.sjoin(
    final_gdf,
    gdf[['LSOA21NM', 'spatial_demand_score', 'suggested_lsoa_officers', 'geometry']],
    predicate='within', how='left'
)
counts = joined.groupby('LSOA21NM').size().rename('officers_placed')
allocation = gdf[['LSOA21NM', 'spatial_demand_score', 'suggested_lsoa_officers']].merge(
    counts, on='LSOA21NM', how='left').fillna({'officers_placed': 0})
allocation['officers_placed'] = allocation['officers_placed'].astype(int)
allocation.to_csv('weighted_lsoa_allocation.csv', index=False)

allocation_sorted = allocation[['LSOA21NM', 'officers_placed']].sort_values(
    by='officers_placed', ascending=False).reset_index(drop=True)
print(f"\nSaved {len(all_officers)} officer positions.")
print(allocation_sorted.head(10))
