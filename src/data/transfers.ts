import { researchSnapshot } from "./researchSnapshot.generated";

export interface Transfer {
  origin: string;
  destination: string;
  headcount: number;
  haversineMiles: number;
  officerMiles: number;
}

export const transfers: Transfer[] = researchSnapshot.transfers.map((transfer) => ({ ...transfer }));

export function originsFor(forceName: string): Transfer[] {
  return transfers.filter((t) => t.destination === forceName);
}

export function destinationsFor(forceName: string): Transfer[] {
  return transfers.filter((t) => t.origin === forceName);
}
