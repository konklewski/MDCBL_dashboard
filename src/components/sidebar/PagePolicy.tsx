import type { Force } from "@/data/forces";
import { originsFor, destinationsFor } from "@/data/transfers";
import { lloydAllocation } from "@/data/lloydAllocation.generated";
import { ArrowRight } from "lucide-react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const fmt = (n: number) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// Low → high officer-count colour ramp (amber → deep red), matching the
// Demand-tab demand chart so the two tabs read consistently.
function officerColor(t: number): string {
  const c = Math.max(0, Math.min(1, t));
  const lerp = (a: number, b: number) => Math.round(a + (b - a) * c);
  // #fcd34d (low) → #b91c1c (high)
  return `rgb(${lerp(252, 185)}, ${lerp(211, 28)}, ${lerp(77, 28)})`;
}

const gifSlug = (name: string) => name.replace(/ & /g, "_and_").replace(/ /g, "_");

export function PagePolicy({ force }: { force: Force }) {
  const isSurplus = force.status === "surplus";
  const isDeficit = force.status === "deficit";
  const rows = isDeficit ? originsFor(force.name) : destinationsFor(force.name);
  const statusLabel = isSurplus ? "OVER-ALLOCATED · SURPLUS" : isDeficit ? "UNDER-ALLOCATED · DEFICIT" : "BALANCED";
  // Colour matches the map flow lines: a deficit force GAINS officers (inbound,
  // green = surplus token); a surplus force SHEDS officers (outbound, red = deficit token).
  const statusTone = isDeficit ? "surplus" : isSurplus ? "deficit" : "data";

  return (
    <div className="p-4 space-y-4">
      <div className={`border border-${statusTone}/50 bg-${statusTone}/10 p-3`}>
        <div className={`font-mono text-[10px] tracking-[0.18em] uppercase text-${statusTone}`}>
          Spatial LP · External Redistribution
        </div>
        <div className="mt-1 text-xs text-foreground leading-relaxed">
          According to the results of the Spatial Linear Programming optimization, the{" "}
          <span className="font-medium">{force.name}</span> territorial police force is determined to be operationally{" "}
          <span className={`text-${statusTone} font-medium`}>{statusLabel}</span>.
        </div>
      </div>

      <div className="border border-border-strong p-4 bg-background/40">
        <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-muted-foreground mb-3">
          Headcount Shift Visualizer
        </div>
        <div className="flex items-center justify-between gap-3">
          <Big label="Initial FTE" value={fmt(force.baselineFTE)} tone="muted" />
          <ArrowRight className={`h-6 w-6 text-${statusTone}`} />
          <Big label="Proposed FTE" value={fmt(force.proposedFTE)} tone={statusTone} />
        </div>
        <div className="mt-3 font-mono text-[11px] text-muted-foreground text-center">
          NET Δ <span className={`text-${statusTone}`}>{force.netShift >= 0 ? "+" : ""}{fmt(force.netShift)}</span> officers
        </div>
      </div>

      <Section title={`Logistical Routing · ${rows.length} ${isDeficit ? "inbound" : "outbound"} legs`}>
        {rows.length === 0 ? (
          <div className="border border-border-strong p-3 bg-background/40 text-xs text-muted-foreground">
            No active transfer legs for this force in the optimized solution.
          </div>
        ) : (
          <div className="border border-border-strong bg-background/40 overflow-hidden">
            <div className="grid grid-cols-[1fr_auto_auto] gap-2 px-3 py-2 border-b border-border font-mono text-[9px] tracking-wider uppercase text-muted-foreground">
              <span>{isDeficit ? "Origin" : "Destination"}</span>
              <span className="text-right">Officers</span>
              <span className="text-right">Haversine</span>
            </div>
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[1fr_auto_auto] gap-2 px-3 py-2 border-b border-border last:border-b-0 text-xs">
                <span className="text-foreground truncate">{isDeficit ? r.origin : r.destination}</span>
                <span className="font-mono text-data text-right">{fmt(r.headcount)}</span>
                <span className="font-mono text-muted-foreground text-right">{r.haversineMiles.toFixed(1)} mi</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title="Internal LSOA Deployment · Weighted Lloyd's Allocation">
        <LloydPlayer force={force} />
      </Section>
    </div>
  );
}

function LloydPlayer({ force }: { force: Force }) {
  const available = (lloydAllocation.animationForces as readonly string[]).includes(force.name);
  const alloc = (lloydAllocation.byForce as unknown as Record<string, {
    totalOfficers: number;
    lsoaCount: number;
    topLsoas: readonly { name: string; code: string; officers: number }[];
  }>)[force.name];

  if (!available || !alloc) {
    return (
      <div className="border border-border-strong bg-background/40 p-3">
        <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-deficit">
          Animation unavailable for this force
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          No internal Weighted Lloyd's officer-placement animation or allocation table was
          generated for <span className="text-foreground">{force.name}</span>.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-border-strong bg-background/40">
      <img
        src={`/animations/${gifSlug(force.name)}_weighted.gif`}
        alt={`Weighted Lloyd's officer allocation animation for ${force.name}`}
        loading="lazy"
        className="w-full border-b border-border-strong bg-black/20"
      />

      <div className="p-3 space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Big label="Officers Placed" value={fmt(alloc.totalOfficers)} tone="data" />
          <Big label="LSOAs Covered" value={fmt(alloc.lsoaCount)} tone="muted" />
        </div>

        <div>
          <div className="font-mono text-[9px] tracking-[0.18em] uppercase text-muted-foreground mb-1.5">
            How to read the animation
          </div>
          <div className="flex flex-col gap-1 font-mono text-[10px] text-muted-foreground">
            <span className="flex items-center gap-2">
              <span className="inline-block h-2 w-5 rounded-sm" style={{ background: "linear-gradient(90deg,#ffeda0,#f03b20)" }} />
              Map shading = LSOA spatial demand (pale = low, red = high crime harm)
            </span>
            <span className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: "steelblue" }} />
              Blue dots = fixed anchor officers (hex grid for baseline coverage)
            </span>
            <span className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: "crimson" }} />
              Red dots = free officers migrating each iteration toward demand
            </span>
          </div>
          <p className="mt-1.5 text-[10px] leading-relaxed text-muted-foreground">
            Weighted Lloyd's iteratively moves each free officer to the demand-weighted centroid of its
            Voronoi cell, minimising expected travel distance to crime. Watch red dots converge on the
            red hotspots; anchors stay put to guarantee minimum spatial coverage.
          </p>
        </div>

        <LloydTopLsoaChart topLsoas={alloc.topLsoas} />
      </div>
    </div>
  );
}

function LloydTopLsoaChart({
  topLsoas,
}: {
  topLsoas: readonly { name: string; code: string; officers: number }[];
}) {
  const maxOfficers = Math.max(...topLsoas.map((l) => l.officers), 1);
  const data = topLsoas.map((l) => {
    const tokens = l.name.trim().split(/\s+/);
    return {
      name: l.name,
      shortName: tokens.slice(-1)[0] || l.name.slice(0, 8),
      officers: l.officers,
      officerShare: l.officers / maxOfficers,
    };
  });

  return (
    <div>
      <div className="font-mono text-[9px] tracking-[0.18em] uppercase text-muted-foreground mb-1.5">
        Top LSOAs by Officers Placed · Weighted Lloyd's
      </div>
      <div className="border border-border-strong bg-background/40">
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: -16, bottom: 28 }}>
              <XAxis
                dataKey="shortName"
                tick={{ fill: "#a1a1aa", fontSize: 9 }}
                angle={-35}
                textAnchor="end"
                interval={0}
                stroke="#3f3f46"
              />
              <YAxis
                tick={{ fill: "#a1a1aa", fontSize: 9 }}
                stroke="#3f3f46"
                label={{
                  value: "Officers placed",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#a1a1aa",
                  fontSize: 9,
                  offset: 14,
                }}
              />
              <Tooltip content={<LloydBarTip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
              <Bar dataKey="officers">
                {data.map((d, i) => (
                  <Cell key={i} fill={officerColor(d.officerShare)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="border-t border-border px-3 py-2">
          <p className="text-[10px] leading-relaxed text-muted-foreground">
            Each bar = 1 LSOA (label = LSOA name suffix). Height &amp; colour = officers placed by
            the Weighted Lloyd's allocation (amber low → red high). Hover for the full LSOA name.
          </p>
        </div>
      </div>
    </div>
  );
}

function LloydBarTip({ active, payload }: { active?: boolean; payload?: any[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="border border-border-strong bg-surface px-2.5 py-1.5 font-mono text-[10px] text-foreground shadow-xl">
      <div className="mb-1 max-w-[180px] truncate text-data">{d.name}</div>
      <div className="flex justify-between gap-3">
        <span className="text-muted-foreground">Officers placed</span>
        <span>{fmt(d.officers)}</span>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-muted-foreground mb-2">{title}</div>
      {children}
    </div>
  );
}

function Big({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex-1 text-center">
      <div className="font-mono text-[9px] tracking-wider uppercase text-muted-foreground">{label}</div>
      <div className={`mt-1 text-2xl font-mono text-${tone}`}>{value}</div>
    </div>
  );
}
