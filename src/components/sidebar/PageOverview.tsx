import type { Force } from "@/data/forces";

const fmt = (n: number) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const fmtMaybe = (n: number | null, suffix = "") => (n == null ? "Not available" : `${fmt(n)}${suffix}`);
const fmtPct = (n: number | null) => (n == null ? "Not available" : `${(n * 100).toFixed(1)}%`);

export function PageOverview({ force }: { force: Force }) {
  const totalCrime = Object.values(force.crimeByCategory).reduce((s, n) => s + n, 0);
  // Match map flow lines: deficit force gains officers (green), surplus sheds (red).
  const statusTone = force.status === "deficit" ? "surplus" : force.status === "surplus" ? "deficit" : "data";
  return (
    <div className="p-4 space-y-4">
      <Section title="General Information">
        <Grid>
          <Stat label="System ID" value={force.id} mono />
          <Stat label="Area of Control" value={fmtMaybe(force.areaSqMi, " mi²")} />
          <Stat label="Baseline Officers (FTE)" value={fmt(force.baselineFTE)} />
          <Stat label="Core Grant 2025-26" value={`£${fmt(Math.round(force.coreGrant2025_26))}`} />
          <Stat label="Stop & Search Hit Rate" value={fmtPct(force.research.hitRate)} />
        </Grid>
      </Section>

      <Section title="Operational Status">
        <div className="border border-border-strong p-3 bg-background/40">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">
              LP Allocation Delta
            </span>
            <span className={`text-2xl font-mono text-${statusTone}`}>
              {force.netShift >= 0 ? "+" : ""}{fmt(force.netShift)}
            </span>
          </div>
          <div className="mt-2 text-xs text-muted-foreground leading-relaxed">
            Proposed FTE from backend transfer solution:{" "}
            <span className="font-mono text-foreground">{fmt(force.proposedFTE)}</span>.
            Allocation uses 2026 forecast CHI and force-level stop-search efficiency.
          </div>
        </div>
      </Section>

      <Section title={totalCrime > 0 ? `Recorded Crime · 2025 · ${fmt(totalCrime)} total` : "Recorded Crime · 2025"}>
        {totalCrime === 0 ? (
          <Missing
            title="No 2025 crime data published for this force"
            body="Greater Manchester Police withdrew from the police.uk open-data feed, so no per-category street counts exist for 2025. All other forces show observed counts from street_from_2021.parquet."
          />
        ) : (
          <div className="border border-border-strong divide-y divide-border">
            {Object.entries(force.crimeByCategory).map(([cat, n]) => {
              const pct = (n / totalCrime) * 100;
              return (
                <div key={cat} className="px-3 py-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-foreground">{cat}</span>
                    <span className="font-mono text-[11px] text-muted-foreground">{fmt(n)}</span>
                  </div>
                  <div className="h-1 bg-border overflow-hidden">
                    <div className="h-full bg-data" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>
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
function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-2">{children}</div>;
}
function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="border border-border-strong p-2.5 bg-background/40">
      <div className="font-mono text-[9px] tracking-wider uppercase text-muted-foreground">{label}</div>
      <div className={`mt-1 text-sm text-foreground ${mono ? "font-mono" : ""}`}>{value}</div>
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
