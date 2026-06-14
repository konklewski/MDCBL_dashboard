import type { Force } from "@/data/forces";
import { NATIONAL_AVG_IMD, forces } from "@/data/forces";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

// ── IMD radar config ─────────────────────────────────────────────────────────
// Each IMD domain is on a DIFFERENT native scale (income = rate ~0.06-0.20,
// health = z-score ~-1..+1, education/housing = scores ~11-33). Plotting raw
// values on one shared radial axis crushes the small-scale domains to the
// centre so they look identical / unmodelled. We min-max normalise each domain
// across all 38 forces to 0-100 so every spoke is comparable, then map the real
// national average onto the same transform. Raw values stay visible in tooltip.
const DOMAIN_KEYS = ["income", "health", "education", "housing"] as const;
type DomainKey = (typeof DOMAIN_KEYS)[number];
const DOMAIN_LABELS: Record<DomainKey, string> = {
  income: "Income",
  health: "Health",
  education: "Education",
  housing: "Housing & Access",
};

// Per-domain min/max across every force (computed once at module load).
const DOMAIN_RANGES: Record<DomainKey, { min: number; max: number }> = (() => {
  const out = {} as Record<DomainKey, { min: number; max: number }>;
  for (const k of DOMAIN_KEYS) {
    const vals = forces.map((f) => f.imd[k]).filter((v): v is number => v != null);
    out[k] = vals.length ? { min: Math.min(...vals), max: Math.max(...vals) } : { min: 0, max: 1 };
  }
  return out;
})();

const norm = (k: DomainKey, v: number | null): number => {
  if (v == null) return 0;
  const { min, max } = DOMAIN_RANGES[k];
  if (max === min) return 50;
  return ((v - min) / (max - min)) * 100;
};

const fmtRaw = (k: DomainKey, v: number | null): string =>
  v == null ? "n/a" : k === "income" ? v.toFixed(3) : v.toFixed(2);

// Low → high demand colour ramp (amber → deep red).
function demandColor(t: number): string {
  const c = Math.max(0, Math.min(1, t));
  const lerp = (a: number, b: number) => Math.round(a + (b - a) * c);
  // #fcd34d (low) → #b91c1c (high)
  return `rgb(${lerp(252, 185)}, ${lerp(211, 28)}, ${lerp(77, 28)})`;
}

export function PageDemand({ force }: { force: Force }) {
  const hasImd = DOMAIN_KEYS.every((k) => force.imd[k] != null);

  const radarData = DOMAIN_KEYS.map((k) => ({
    domain: DOMAIN_LABELS[k],
    Force: norm(k, force.imd[k]),
    National: norm(k, NATIONAL_AVG_IMD[k] ?? null),
    rawForce: fmtRaw(k, force.imd[k]),
    rawNational: fmtRaw(k, NATIONAL_AVG_IMD[k] ?? null),
  }));

  return (
    <div className="p-4 space-y-4">
      <Section title="Modeling Methodology">
        <p className="text-xs text-muted-foreground leading-relaxed border border-border-strong p-3 bg-background/40">
          2026 Random Forest CHI forecast using 2021-2025 historical data, previous-year CHI,
          lagged spatial-neighbour CHI, and force-level deprivation features. Outputs feed the LP
          optimiser as force-level demand coefficients.
        </p>
      </Section>

      <Section title="Deprivation Profile · IMD vs National Average">
        {!hasImd ? (
          <Missing
            title="IMD force profile unavailable in current cache"
            body="IoD2019 scores did not match this force in the current backend cache."
          />
        ) : (
          <div className="border border-border-strong bg-background/40">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarData} outerRadius="68%">
                  <PolarGrid stroke="#3f3f46" />
                  <PolarAngleAxis dataKey="domain" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={{ fill: "#52525b", fontSize: 9 }} stroke="#3f3f46" />
                  <Radar name="National avg" dataKey="National" stroke="#a1a1aa" fill="#a1a1aa" fillOpacity={0.12} />
                  <Radar name="This force" dataKey="Force" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.35} />
                  <Tooltip content={<RadarTip />} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <Legend
              items={[
                { color: "#22d3ee", label: "This force" },
                { color: "#a1a1aa", label: "National average" },
              ]}
              note="Each spoke min-max scaled 0-100 across all 38 forces (0 = least deprived force, 100 = most). Hover for real IMD values. Higher = more deprived."
            />
          </div>
        )}
      </Section>

      <Section title="Micro-Level Analysis · LSOA Layer">
        {force.lsoaDemandCells.length === 0 ? (
          <Missing
            title="LSOA demand surface unavailable"
            body="No LSOA demand cells were serialized for this force."
          />
        ) : (
          <LsoaPointLayer cells={force.lsoaDemandCells} />
        )}
      </Section>
    </div>
  );
}

function LsoaPointLayer({ cells }: { cells: Force["lsoaDemandCells"] }) {
  const topCells = cells.slice(0, 80);
  const lats = topCells.map((c) => c.latitude);
  const lngs = topCells.map((c) => c.longitude);
  const scores = topCells.map((c) => c.demandScore);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const maxScore = Math.max(...scores, 0.0001);
  const xFor = (lng: number) => ((lng - minLng) / ((maxLng - minLng) || 1)) * 88 + 6;
  const yFor = (lat: number) => 94 - ((lat - minLat) / ((maxLat - minLat) || 1)) * 88;

  return (
    <div className="border border-border-strong bg-background/40 p-2">
      <div className="relative">
        <svg viewBox="0 0 100 100" className="h-56 w-full" role="img" aria-label="LSOA demand point layer">
          <rect x="0" y="0" width="100" height="100" fill="rgba(47, 110, 168, 0.05)" />
          {/* render low demand first so hottest LSOAs sit on top */}
          {[...topCells]
            .map((cell, index) => ({ cell, index }))
            .sort((a, b) => a.cell.demandScore - b.cell.demandScore)
            .map(({ cell, index }) => {
              const t = cell.demandScore / maxScore;
              const intensity = Math.max(0.18, t);
              return (
                <circle
                  key={`${cell.code}-${index}`}
                  cx={xFor(cell.longitude)}
                  cy={yFor(cell.latitude)}
                  r={2 + intensity * 5}
                  fill={demandColor(t)}
                  opacity={0.35 + intensity * 0.5}
                >
                  <title>{`${cell.name}\nDemand ${cell.demandScore.toFixed(3)} · ${Math.round(
                    cell.suggestedOfficers,
                  )} officers · harm ${Math.round(cell.crimeHarm).toLocaleString()}`}</title>
                </circle>
              );
            })}
        </svg>
        {/* geographic axis hints */}
        <span className="pointer-events-none absolute bottom-1 right-2 font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
          W → E (longitude)
        </span>
        <span className="pointer-events-none absolute left-1 top-1 font-mono text-[8px] uppercase tracking-wider text-muted-foreground">
          ↑ N (latitude)
        </span>
      </div>
      <Legend
        gradient
        note={`Geographic map of this force's ${topCells.length} highest-demand LSOAs, each dot placed at its real lat/lon. Dot size & colour = spatial demand score (amber low → red high).`}
      />
      <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
        <span>Cells {topCells.length}</span>
        <span>Max score {maxScore.toFixed(3)}</span>
        <span>Peak {topCells[0]?.suggestedOfficers ?? 0} FTE</span>
      </div>
    </div>
  );
}

function RadarTip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="border border-border-strong bg-surface px-2.5 py-1.5 font-mono text-[10px] text-foreground shadow-xl">
      <div className="mb-1 text-data">{p.domain}</div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Force</span>
        <span>
          {p.rawForce} <span className="text-muted-foreground">({Math.round(p.Force)}/100)</span>
        </span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">National</span>
        <span>
          {p.rawNational} <span className="text-muted-foreground">({Math.round(p.National)}/100)</span>
        </span>
      </div>
    </div>
  );
}

function Legend({
  items,
  gradient,
  note,
}: {
  items?: { color: string; label: string }[];
  gradient?: boolean;
  note: string;
}) {
  return (
    <div className="border-t border-border px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {items?.map((it) => (
          <span key={it.label} className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: it.color }} />
            {it.label}
          </span>
        ))}
        {gradient && (
          <span className="flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">
            <span className="text-[9px]">low</span>
            <span
              className="inline-block h-2 w-16 rounded-full"
              style={{ background: `linear-gradient(90deg, ${demandColor(0)}, ${demandColor(1)})` }}
            />
            <span className="text-[9px]">high demand</span>
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[10px] leading-relaxed text-muted-foreground">{note}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-muted-foreground mb-2">
        {title}
      </div>
      {children}
    </div>
  );
}

function Missing({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-border-strong bg-background/40 p-3">
      <div className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">{title}</div>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}
