import { researchSnapshot } from "./researchSnapshot.generated";
import { forceFacts } from "./forceFacts.generated";

export interface Force {
  id: string;
  name: string;
  code: string;
  areaSqMi: number | null;
  populationDensity: number | null;
  baselineFTE: number;
  proposedFTE: number;
  safetyIndex: number | null;
  status: "surplus" | "deficit" | "balanced";
  netShift: number;
  coreGrant2025_26: number;
  crimeByCategory: Record<string, number>;
  imd: {
    income: number | null;
    health: number | null;
    education: number | null;
    housing: number | null;
    services: number | null;
  };
  topLsoas: {
    name: string;
    code?: string;
    latitude?: number | null;
    longitude?: number | null;
    scores: Record<string, number>;
  }[];
  lsoaDemandCells: {
    name: string;
    code: string;
    latitude: number;
    longitude: number;
    demandScore: number;
    crimeHarm: number;
    suggestedOfficers: number;
  }[];
  research: {
    totalChi: number | null;
    predictedChi: number | null;
    spatialLagChi: number | null;
    hitRate: number | null;
    successCount: number | null;
    searchCount: number | null;
    latitude: number | null;
    longitude: number | null;
    sourceCompleteness: string;
  };
  missingComputedFields: string[];
}

export const researchBackendSnapshot = researchSnapshot;

// Crime categories sorted by count, descending (nicer Overview rendering).
function sortCounts(counts: Record<string, number>): Record<string, number> {
  return Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1]));
}

// The LSOA demand surface groups crime by the *reporting* force. police.uk snaps
// some City of London Police crimes to anonymised map points in neighbouring
// Metropolitan-borough LSOAs (Tower Hamlets, Hackney, Islington…), inflating its
// LSOA list to ~278. City of London Police's statutory jurisdiction is the City
// of London local authority — the "City of London ###" LSOAs — so keep only those.
function jurisdictionFilter<T extends { name: string }>(forceName: string, rows: T[]): T[] {
  if (forceName === "City of London") {
    return rows.filter((row) => row.name.startsWith("City of London"));
  }
  return rows;
}

export const forces: Force[] = researchSnapshot.forces.map((force) => ({
  ...force,
  status: force.status as Force["status"],
  // Overlay computed land area (sq mi) + observed 2025 crime counts. Snapshot
  // ships these null/empty; forceFacts.generated.ts derives them from the ONS
  // PFA24 shapefile and the police.uk street_from_2021 parquet.
  areaSqMi: forceFacts[force.name]?.areaSqMi ?? force.areaSqMi,
  crimeByCategory: sortCounts(forceFacts[force.name]?.crimeByCategory2025 ?? force.crimeByCategory),
  imd: { ...force.imd },
  topLsoas: jurisdictionFilter(
    force.name,
    force.topLsoas.map((lsoa) => ({
      name: lsoa.name,
      code: lsoa.code,
      latitude: lsoa.latitude,
      longitude: lsoa.longitude,
      scores: { ...lsoa.scores },
    })),
  ),
  lsoaDemandCells: jurisdictionFilter(force.name, [...(force.lsoaDemandCells ?? [])]),
  missingComputedFields: [...force.missingComputedFields],
}));

export const forceByName = new Map(forces.map((f) => [f.name, f]));
export const forceById = new Map(forces.map((f) => [f.id, f]));

export const NATIONAL_AVG_IMD = researchSnapshot.nationalAvgImd ?? {
  income: null,
  health: null,
  education: null,
  housing: null,
  services: null,
};

export const CRIME_CATEGORIES = Object.keys(researchSnapshot.crimeSeverityMedians).filter(
  (name) => name !== "Anti-social behavior",
);
