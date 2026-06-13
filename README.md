# Force Flow

An interactive dashboard for spatial reallocation of police officers across the
territorial forces of England. It visualises each force's optimised officer
allocation, the inter-force transfer flows that balance supply against forecast
demand, and an internal (within-force) deployment view down to LSOA level.

The project has two parts:

- **Frontend** (`src/`) — a React + TanStack Start single-page dashboard with a
  Mapbox map, per-force sidebar (Overview / Demand / Policy), and flow overlays.
- **Backend** (`backend/research_pipeline/`) — a Python pipeline that turns the
  raw crime, deprivation and funding data into the optimised allocation and
  writes the static data files the frontend reads.

The frontend consumes pre-generated data files, so it runs without the backend.
The backend is only needed to regenerate those files.

## Tech stack

| Layer | Tools |
| --- | --- |
| UI | React 19, TanStack Start / Router (SSR), Tailwind CSS v4, Zustand |
| Maps & charts | Mapbox GL, Recharts |
| Data pipeline | Python, pandas, scikit-learn, SciPy (`linprog`), geopandas |

## Running the dashboard

```bash
bun install
bun run dev      # start the dev server
bun run build    # production build (client + SSR server) into dist/
bun run preview  # serve the production build
```

The map needs a Mapbox access token. A default token is bundled, but you can
override it with an environment variable:

```bash
VITE_MAPBOX_TOKEN=pk.your_token_here bun run dev
```

## Project layout

```
src/
  components/
    header/      global header + force search
    map/         Mapbox map, flow overlays, view toggles
    sidebar/     per-force panels: Overview, Demand, Policy
    ui/          shared UI primitives
  data/          generated data the dashboard reads (see below)
  routes/        TanStack file-based routes (__root.tsx is the shell)
  state/         Zustand store
public/animations/             per-force internal-allocation animations
backend/research_pipeline/     data pipeline (see its own README)
```

## Generated data

The frontend reads three generated files under `src/data/`:

- `researchSnapshot.generated.ts` — forces, demand forecast and transfer legs,
  produced by `backend/research_pipeline/pipeline.py`.
- `forceFacts.generated.ts` — per-force land area and observed 2025 crime counts,
  produced by `backend/research_pipeline/scripts/generate_force_facts.py`.
- `lloydAllocation.generated.ts` — internal LSOA officer-allocation summaries
  that accompany the per-force animations in `public/animations/`.

These files are committed, so the app builds and runs as-is. See the backend
README for how to regenerate them.
