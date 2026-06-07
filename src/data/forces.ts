import { researchSnapshot } from "./researchSnapshot.generated";

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
  topLsoas: { name: string; scores: Record<string, number> }[];
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

export const forces: Force[] = researchSnapshot.forces.map((force) => ({
  ...force,
  status: force.status as Force["status"],
  crimeByCategory: { ...force.crimeByCategory },
  imd: { ...force.imd },
  topLsoas: force.topLsoas.map((lsoa) => ({ name: lsoa.name, scores: { ...lsoa.scores } })),
  missingComputedFields: [...force.missingComputedFields],
}));

export const forceByName = new Map(forces.map((f) => [f.name, f]));
export const forceById = new Map(forces.map((f) => [f.id, f]));

export const NATIONAL_AVG_IMD = { income: null, health: null, education: null, housing: null, services: null };

export const CRIME_CATEGORIES = Object.keys(researchSnapshot.crimeSeverityMedians).filter(
  (name) => name !== "Anti-social behavior",
);
