"""
Baseline Comparison & Crime Simulation
=======================================
Loads weighted officer positions from simulation2_weighted.py, builds two
baselines (hex-grid uniform and RTM-recommended), simulates crime dispatch
for all three, and produces a 2×2 allocation map and a CDF plot.

Prerequisites (produced by simulation2_weighted.py):
  - weighted_officer_positions.npy
  - density_pts.npy
  - lsoaJoinedTerritory/lsoaJoinedTerritory.shp
  - lsoa_harm_surface.csv

SIMULATION MODEL
────────────────
Crimes arrive each time step as a Negative Binomial process:
  n_crimes ~ NB(r, p) via gamma-Poisson mixture (works for non-integer r):
    λ ~ Gamma(r, crime_rate / r)
    n_crimes ~ Poisson(λ)
This gives mean = crime_rate and variance = crime_rate + crime_rate²/r.
Lower r → more overdispersion (burstier arrivals) than Poisson.
Each crime occupies the nearest available officer for OFFICER_BUSY_ITERS steps.

Limitations:
  - Euclidean distance, not network distance
  - Single officer per crime
"""

import json
import numpy as np
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.prepared import prep

# ── Load shared config ───────────────────────────────────────────────────────
with open('config.json') as _f:
    _cfg = json.load(_f)

FORCE              = _cfg['force']
RISK_FLOOR         = _cfg['risk_floor']
R_COVERAGE_M       = _cfg['r_coverage_m']
N_DENSITY_SAMPLES  = _cfg['n_density_samples']
N_CRIMES           = _cfg['n_crimes']
CRIME_RATE_PER_STEP = _cfg['crime_rate_per_step']
NB_DISPERSION      = _cfg['nb_dispersion']        # r: lower = burstier
OFFICER_BUSY_ITERS = _cfg['officer_busy_iters']   # steps officer is occupied
N_SIM_STEPS        = int(N_CRIMES / CRIME_RATE_PER_STEP)
SEED               = _cfg['seed']
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
lsoa_areas = gdf.geometry.area.to_numpy()
polygon    = gdf.geometry.union_all()

print(f"Force: {FORCE} | LSOAs: {len(gdf)} | N_TOTAL: {N_TOTAL}")

# ═══════════════════════════════════════════════════════════
# LOAD WEIGHTED OFFICER POSITIONS
# ═══════════════════════════════════════════════════════════
all_officers = np.load('weighted_officer_positions.npy')
print(f"Loaded {len(all_officers)} weighted officer positions.")

# ═══════════════════════════════════════════════════════════
# DENSITY FIELD  (crime locations for simulation)
# ═══════════════════════════════════════════════════════════
try:
    density_pts = np.load('density_pts.npy')
    print(f"Loaded {len(density_pts)} density sample points.")
except FileNotFoundError:
    print(f"density_pts.npy not found — rebuilding ({N_DENSITY_SAMPLES} pts)...")
    crime_freq  = lsoa_risks * lsoa_areas
    cp          = crime_freq / crime_freq.sum()
    n_per       = (N_DENSITY_SAMPLES * cp).astype(int)
    n_per[np.argmax(crime_freq)] += N_DENSITY_SAMPLES - n_per.sum()
    pts_list = []
    for geom, n in zip(gdf.geometry, n_per):
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
        pts_list.extend(sampled[:n])
    density_pts = np.array(pts_list)

# Uniform probabilities: density_pts are already sampled ∝ demand×area,
# so their spatial density encodes the crime distribution — no further weighting.
sample_probs = np.ones(len(density_pts)) / len(density_pts)

# ═══════════════════════════════════════════════════════════
# HEX-GRID UNIFORM BASELINE  (exactly N_TOTAL officers)
# ═══════════════════════════════════════════════════════════
# Derive grid spacing so the hex grid yields approximately N_TOTAL points.
# For a hex lattice: area_per_point = dx * dy = R * R*sqrt(3)/2
# → R_target = sqrt(2 * total_area / (sqrt(3) * N_TOTAL))
# Then trim or pad to hit N_TOTAL exactly.
print("\nBuilding hex-grid uniform baseline...")

total_area   = lsoa_areas.sum()
R_uniform    = np.sqrt(2 * total_area / (np.sqrt(3) * N_TOTAL))
minx, miny, maxx, maxy = polygon.bounds
dx_u = R_uniform
dy_u = R_uniform * np.sqrt(3) / 2
prepared_polygon = prep(polygon)

uniform_list = []
row = 0
y = miny
while y <= maxy + dy_u:
    x_off = (dx_u / 2) if (row % 2) else 0.0
    x = minx + x_off
    while x <= maxx + dx_u:
        if prepared_polygon.contains(Point(x, y)):
            uniform_list.append([x, y])
        x += dx_u
    y += dy_u
    row += 1

uniform_pts = np.array(uniform_list)

# Trim or pad to exactly N_TOTAL
if len(uniform_pts) > N_TOTAL:
    keep = np.random.choice(len(uniform_pts), N_TOTAL, replace=False)
    uniform_pts = uniform_pts[keep]
elif len(uniform_pts) < N_TOTAL:
    n_extra = N_TOTAL - len(uniform_pts)
    extra = []
    while len(extra) < n_extra:
        xs = np.random.uniform(minx, maxx, n_extra * 6)
        ys = np.random.uniform(miny, maxy, n_extra * 6)
        for x, y in zip(xs, ys):
            if prepared_polygon.contains(Point(x, y)):
                extra.append([x, y])
    uniform_pts = np.vstack([uniform_pts, extra[:n_extra]])

np.save('uniform_officer_positions.npy', uniform_pts)
print(f"Hex-grid uniform baseline: {len(uniform_pts)} officers (= N_TOTAL {N_TOTAL}).")

# ═══════════════════════════════════════════════════════════
# RTM-RECOMMENDED PLACEMENT
# ═══════════════════════════════════════════════════════════
print("Building RTM-recommended placement...")
rtm_n = gdf['suggested_lsoa_officers'].fillna(0).round().astype(int).to_numpy()
rtm_pts_list = []
for geom, n in zip(gdf.geometry, rtm_n):
    if n <= 0:
        continue
    pgeom = prep(geom)
    lx, ly, hx, hy = geom.bounds
    pts = []
    while len(pts) < n:
        xs = np.random.uniform(lx, hx, n * 6)
        ys = np.random.uniform(ly, hy, n * 6)
        for x, y in zip(xs, ys):
            if pgeom.contains(Point(x, y)):
                pts.append([x, y])
    rtm_pts_list.extend(pts[:n])
rtm_pts = np.array(rtm_pts_list)
print(f"RTM placement: {len(rtm_pts)} officers across {(rtm_n > 0).sum()} LSOAs")

# ═══════════════════════════════════════════════════════════
# CRIME SIMULATION
# ═══════════════════════════════════════════════════════════
def simulate_crimes(officer_positions, n_steps, crime_rate, nb_dispersion,
                    busy_iters, density_pts, crime_probs):
    """
    Simulate crimes arriving as a Negative Binomial process over n_steps.

    Uses a gamma-Poisson mixture (valid for non-integer dispersion r):
        λ_t ~ Gamma(r, crime_rate / r)
        arrivals_t ~ Poisson(λ_t)
    Mean = crime_rate, Variance = crime_rate + crime_rate²/r per step.
    Lower r → burstier (more overdispersed) arrivals than Poisson.

    Each crime occupies the nearest available officer for busy_iters steps.

    Returns
    -------
    travel_distances : list[float]  — Euclidean distance (m) per served crime
    unserved         : int          — crimes where all officers were busy
    """
    N          = len(officer_positions)
    busy_until = np.zeros(N, dtype=int)
    travel_distances = []
    unserved   = 0

    for step in range(n_steps):
        # Negative Binomial via gamma-Poisson mixture
        lam       = np.random.gamma(nb_dispersion, crime_rate / nb_dispersion)
        n_crimes  = np.random.poisson(lam)
        if n_crimes == 0:
            continue

        crime_idx  = np.random.choice(len(density_pts), size=n_crimes, p=crime_probs)
        crime_locs = density_pts[crime_idx]

        for crime_xy in crime_locs:
            available = np.where(busy_until <= step)[0]
            if len(available) == 0:
                unserved += 1
                continue

            avail_pos  = officer_positions[available]
            tree_avail = cKDTree(avail_pos)
            dist, idx  = tree_avail.query(crime_xy)

            officer_id = available[idx]
            travel_distances.append(dist)
            busy_until[officer_id] = step + busy_iters

    return travel_distances, unserved

# ═══════════════════════════════════════════════════════════
# RUN SIMULATIONS
# ═══════════════════════════════════════════════════════════
print(f"\nSimulating {N_CRIMES} crimes (NB, r={NB_DISPERSION}) — weighted placement...")
w_dists, w_unserved = simulate_crimes(
    all_officers, N_SIM_STEPS, CRIME_RATE_PER_STEP,
    NB_DISPERSION, OFFICER_BUSY_ITERS, density_pts, sample_probs)

print(f"Simulating — hex-grid uniform baseline...")
u_dists, u_unserved = simulate_crimes(
    uniform_pts, N_SIM_STEPS, CRIME_RATE_PER_STEP,
    NB_DISPERSION, OFFICER_BUSY_ITERS, density_pts, sample_probs)

print(f"Simulating — RTM recommended placement...")
r_dists, r_unserved = simulate_crimes(
    rtm_pts, N_SIM_STEPS, CRIME_RATE_PER_STEP,
    NB_DISPERSION, OFFICER_BUSY_ITERS, density_pts, sample_probs)

w_dists = np.array(w_dists)
u_dists = np.array(u_dists)
r_dists = np.array(r_dists)

# ═══════════════════════════════════════════════════════════
# STATISTICS TABLE
# ═══════════════════════════════════════════════════════════
print(f"\n{'':─<60}")
print(f"{'Metric':<35}  {'Weighted':>8}  {'RTM':>8}  {'Uniform':>8}")
print(f"{'':─<60}")
print(f"{'Crimes responded':<35}  {len(w_dists):>8}  {len(r_dists):>8}  {len(u_dists):>8}")
print(f"{'Unserved (all busy)':<35}  {w_unserved:>8}  {r_unserved:>8}  {u_unserved:>8}")
print(f"{'Mean travel distance (m)':<35}  {w_dists.mean():>8.0f}  {r_dists.mean():>8.0f}  {u_dists.mean():>8.0f}")
print(f"{'Median travel distance (m)':<35}  {np.median(w_dists):>8.0f}  {np.median(r_dists):>8.0f}  {np.median(u_dists):>8.0f}")
print(f"{'90th-pct travel distance (m)':<35}  {np.percentile(w_dists,90):>8.0f}  {np.percentile(r_dists,90):>8.0f}  {np.percentile(u_dists,90):>8.0f}")
print(f"{'Max travel distance (m)':<35}  {w_dists.max():>8.0f}  {r_dists.max():>8.0f}  {u_dists.max():>8.0f}")
print(f"{'':─<60}")
print(f"vs uniform — mean improvement:  weighted {(u_dists.mean()-w_dists.mean())/u_dists.mean()*100:+.1f}%  "
      f"RTM {(u_dists.mean()-r_dists.mean())/u_dists.mean()*100:+.1f}%")

# ═══════════════════════════════════════════════════════════
# ALLOCATION MAPS  (2×2 grid)
# ═══════════════════════════════════════════════════════════
norm = plt.Normalize(vmin=lsoa_risks.min(), vmax=lsoa_risks.max())

fig_maps, axes = plt.subplots(2, 2, figsize=(9, 7))
panels = [
    (axes[0, 0], None,         'Spatial Demand'),
    (axes[0, 1], all_officers, 'Weighted Voronoi'),
    (axes[1, 0], rtm_pts,      'RTM Recommended'),
    (axes[1, 1], uniform_pts,  'Uniform Baseline'),
]

for ax, pts, title in panels:
    gdf.plot(ax=ax, column='spatial_demand_score', cmap='YlOrRd', norm=norm,
             alpha=0.55, edgecolor='grey', linewidth=0.2)
    if pts is not None:
        ax.scatter(pts[:, 0], pts[:, 1], s=1.5, c='steelblue', alpha=0.7, zorder=3)
    ax.set_aspect('equal')
    ax.axis('off')
    subtitle = f'({len(pts)} officers)' if pts is not None else ''
    ax.set_title(f'{title}\n{subtitle}', fontsize=11)

sm = plt.cm.ScalarMappable(cmap='YlOrRd', norm=norm)
sm.set_array([])
fig_maps.colorbar(sm, ax=axes, shrink=0.4, label='Spatial demand score',
                  orientation='horizontal', pad=0.02, fraction=0.03)
fig_maps.suptitle(f'\n{FORCE} Police — Officer Allocation Comparison', fontsize=14, y=1.01)
plt.tight_layout()
plt.show()

# ═══════════════════════════════════════════════════════════
# CDF PLOT
# ═══════════════════════════════════════════════════════════
fig2, ax1 = plt.subplots(figsize=(8, 5))

for dists, label, colour in [
    (w_dists, 'Weighted Voronoi',                      'crimson'),
    (r_dists, 'RTM recommended (uniform within LSOA)', 'darkorange'),
    (u_dists, 'Uniform hex-grid baseline',             'steelblue'),
]:
    sorted_d = np.sort(dists)
    cdf = np.arange(1, len(sorted_d) + 1) / len(sorted_d)
    ax1.plot(sorted_d / 1000, cdf, label=label, color=colour, linewidth=2)

ax1.set_xlabel('Travel distance to nearest available officer (km)')
ax1.set_ylabel('Cumulative proportion of crimes')
ax1.set_title(f'{FORCE} — CDF of response travel distance ({N_CRIMES} simulated crimes)')
ax1.legend()
ax1.grid(alpha=0.3)
plt.show()
