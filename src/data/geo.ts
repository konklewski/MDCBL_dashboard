// Geo helpers: fetch UK police force boundaries, compute centroids, generate great-circle arcs.
import { forces } from "./forces";

export interface FeatureCollection {
  type: "FeatureCollection";
  features: GeoFeature[];
}
export interface GeoFeature {
  type: "Feature";
  properties: Record<string, any>;
  geometry: any;
}

// Public source: official ONS ArcGIS FeatureServer, simplified and returned as WGS84 GeoJSON.
const SOURCES = [
  "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Police_Force_Areas_December_2023_EW_BFE/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson&outSR=4326&returnGeometry=true&generalize=true&maxAllowableOffset=0.003&geometryPrecision=5",
];

const BOUNDARY_FETCH_TIMEOUT_MS = 3500;

async function fetchWithTimeout(url: string): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BOUNDARY_FETCH_TIMEOUT_MS);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export async function fetchForceBoundaries(): Promise<FeatureCollection> {
  for (const url of SOURCES) {
    try {
      const r = await fetchWithTimeout(url);
      if (r.ok) {
        const data = (await r.json()) as FeatureCollection;
        if (data.features?.length) return withMissingForceFeatures(data);
      }
    } catch {
      // try next
    }
  }
  return fallbackForceBoundaries();
}

// Map GeoJSON name property to our internal force name
const NAME_ALIASES: Record<string, string> = {
  "Metropolitan Police": "London forces: Metropolitan Police + City of London Police",
  "City of London": "London forces: Metropolitan Police + City of London Police",
  "Avon and Somerset": "Avon & Somerset",
  "Devon and Cornwall": "Devon & Cornwall",
  "Hampshire": "Hampshire & Isle of Wight",
  "Dyfed-Powys": "Dyfed-Powys",
};

export function normalizeForceName(raw: string | undefined): string | null {
  if (!raw) return null;
  return NAME_ALIASES[raw] ?? raw;
}

const FORCE_CENTERS: Record<string, [number, number]> = {
  "London forces: Metropolitan Police + City of London Police": [-0.12, 51.5],
  "West Midlands": [-1.9, 52.5],
  "Greater Manchester": [-2.24, 53.48],
  "West Yorkshire": [-1.55, 53.8],
  "Thames Valley": [-1.05, 51.75],
  Northumbria: [-1.62, 55.05],
  Merseyside: [-2.98, 53.41],
  "South Yorkshire": [-1.47, 53.38],
  "Hampshire & Isle of Wight": [-1.25, 50.95],
  Kent: [0.52, 51.25],
  Lancashire: [-2.7, 53.85],
  Essex: [0.48, 51.75],
  "Avon & Somerset": [-2.65, 51.35],
  Sussex: [-0.45, 50.95],
  "Devon & Cornwall": [-4.35, 50.55],
  Nottinghamshire: [-1.15, 53.05],
  "South Wales": [-3.45, 51.62],
  Staffordshire: [-2.05, 52.85],
  Cheshire: [-2.62, 53.2],
  Hertfordshire: [-0.22, 51.82],
  Leicestershire: [-1.12, 52.65],
  "West Mercia": [-2.25, 52.25],
  Humberside: [-0.32, 53.7],
  Derbyshire: [-1.55, 53.12],
  Cleveland: [-1.22, 54.58],
  Durham: [-1.6, 54.72],
  Norfolk: [0.95, 52.72],
  Cambridgeshire: [-0.05, 52.35],
  Surrey: [-0.45, 51.25],
  Northamptonshire: [-0.85, 52.28],
  Suffolk: [1.05, 52.18],
  Lincolnshire: [-0.25, 53.15],
  "North Yorkshire": [-1.35, 54.15],
  Bedfordshire: [-0.47, 52.05],
  Cumbria: [-2.9, 54.65],
  Wiltshire: [-1.95, 51.35],
  Gloucestershire: [-2.18, 51.85],
  Warwickshire: [-1.55, 52.28],
  Dorset: [-2.35, 50.75],
  "North Wales": [-3.65, 53.15],
  Gwent: [-3.02, 51.72],
  "Dyfed-Powys": [-4.1, 52.25],
  "Police Scotland (advisory)": [-4.05, 56.65],
};

export function approximateForceCenter(forceName: string): [number, number] | null {
  return FORCE_CENTERS[forceName] ?? null;
}

function withMissingForceFeatures(data: FeatureCollection): FeatureCollection {
  const present = new Set(
    data.features
      .map((feature) => {
        const raw =
          feature.properties?.PFA23NM ||
          feature.properties?.PFA22NM ||
          feature.properties?.PFA20NM ||
          feature.properties?.pfa15nm ||
          feature.properties?.name ||
          feature.properties?.NAME;
        return normalizeForceName(raw);
      })
      .filter(Boolean),
  );

  const missing = forces
    .filter((force) => !present.has(force.name))
    .map((force) => approximateFeature(force.name));

  return {
    type: "FeatureCollection",
    features: [...data.features, ...missing],
  };
}

export function fallbackForceBoundaries(): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: forces.map((force) => approximateFeature(force.name)),
  };
}

function approximateFeature(forceName: string): GeoFeature {
  const [lng, lat] = FORCE_CENTERS[forceName] ?? [-2.6, 54.2];
  const isScotland = forceName === "Police Scotland (advisory)";
  const w = isScotland ? 3.7 : 0.58;
  const h = isScotland ? 3.8 : 0.44;

  return {
    type: "Feature",
    properties: { PFA23NM: forceName, PFA22NM: forceName, name: forceName, approximate: true },
    geometry: {
      type: "Polygon",
      coordinates: [[
        [lng - w / 2, lat - h / 2],
        [lng + w / 2, lat - h / 2],
        [lng + w / 2, lat + h / 2],
        [lng - w / 2, lat + h / 2],
        [lng - w / 2, lat - h / 2],
      ]],
    },
  };
}

// Centroid of a polygon/multipolygon (simple average of outer ring coords)
export function centroid(geom: any): [number, number] {
  const pts: [number, number][] = [];
  const visit = (coords: any) => {
    if (typeof coords[0] === "number") pts.push([coords[0], coords[1]]);
    else for (const c of coords) visit(c);
  };
  visit(geom.coordinates);
  let x = 0,
    y = 0;
  for (const p of pts) {
    x += p[0];
    y += p[1];
  }
  return [x / pts.length, y / pts.length];
}

// Great-circle arc as a curved bezier in screen space (good enough at country scale)
export function arcLine(
  from: [number, number],
  to: [number, number],
  steps = 64,
): [number, number][] {
  const out: [number, number][] = [];
  // midpoint with perpendicular offset to bulge the line
  const mx = (from[0] + to[0]) / 2;
  const my = (from[1] + to[1]) / 2;
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  const dist = Math.sqrt(dx * dx + dy * dy);
  const nx = -dy / (dist || 1);
  const ny = dx / (dist || 1);
  const bulge = dist * 0.25;
  const cx = mx + nx * bulge;
  const cy = my + ny * bulge;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = (1 - t) * (1 - t) * from[0] + 2 * (1 - t) * t * cx + t * t * to[0];
    const y = (1 - t) * (1 - t) * from[1] + 2 * (1 - t) * t * cy + t * t * to[1];
    out.push([x, y]);
  }
  return out;
}
