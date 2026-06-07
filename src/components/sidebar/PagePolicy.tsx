import type { Force } from "@/data/forces";
import { originsFor, destinationsFor } from "@/data/transfers";
import { ArrowRight } from "lucide-react";

const fmt = (n: number) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

export function PagePolicy({ force }: { force: Force }) {
  const isSurplus = force.status === "surplus";
  const isDeficit = force.status === "deficit";
  const rows = isDeficit ? originsFor(force.name) : destinationsFor(force.name);
  const statusLabel = isSurplus ? "OVER-ALLOCATED · SURPLUS" : isDeficit ? "UNDER-ALLOCATED · DEFICIT" : "BALANCED";
  const statusTone = isSurplus ? "surplus" : isDeficit ? "deficit" : "data";

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

      <Section title="Internal LSOA Deployment">
        <div className="border border-border-strong bg-background/40 p-3">
          <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-deficit">
            Not implemented · no source data
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            The previous Lloyd's algorithm player was a visual placeholder. Backend now marks this as missing:
            no research file contains LSOA-level officer placement targets, station capacity constraints,
            response-time objective, or Lloyd/k-means allocation output.
          </p>
        </div>
      </Section>
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
