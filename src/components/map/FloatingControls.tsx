import { useApp } from "@/state/useAppStore";
import { Settings, Box, Square } from "lucide-react";
import { useState } from "react";

export function FloatingControls() {
  const dim = useApp((s) => s.dim);
  const setDim = useApp((s) => s.setDim);
  const prefs = useApp((s) => s.prefs);
  const setPrefs = useApp((s) => s.setPrefs);
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="absolute bottom-3 right-3 flex flex-col items-end gap-2">
        <div className="flex border border-border-strong bg-surface/85 backdrop-blur">
          <button
            onClick={() => setDim("2d")}
            className={
              "h-9 w-9 grid place-items-center font-mono text-[10px] " +
              (dim === "2d" ? "bg-data/15 text-data" : "text-muted-foreground hover:text-foreground")
            }
            title="2D"
          >
            <Square className="h-3.5 w-3.5" />
            <span className="sr-only">2D</span>
          </button>
          <button
            onClick={() => setDim("3d")}
            className={
              "h-9 w-9 grid place-items-center font-mono text-[10px] " +
              (dim === "3d" ? "bg-data/15 text-data" : "text-muted-foreground hover:text-foreground")
            }
            title="3D"
          >
            <Box className="h-3.5 w-3.5" />
          </button>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="h-10 w-10 rounded-full grid place-items-center border border-border-strong bg-surface/85 backdrop-blur text-muted-foreground hover:text-data hover:border-data/50"
          title="Optimization preferences"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>

      {open && (
        <div className="absolute bottom-16 right-3 w-80 border border-border-strong bg-surface/95 backdrop-blur p-4 shadow-2xl">
          <div className="flex items-center justify-between mb-3">
            <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-muted-foreground">
              Optimization Preferences
            </div>
            <button onClick={() => setOpen(false)} className="text-xs text-muted-foreground hover:text-foreground">✕</button>
          </div>

          <Field label={`Stop & Search Efficiency Weighting · ${prefs.efficiencyWeight}%`}>
            <input
              type="range"
              min={0}
              max={100}
              value={prefs.efficiencyWeight}
              onChange={(e) => setPrefs({ efficiencyWeight: +e.target.value })}
              className="w-full accent-data"
            />
          </Field>

          <Field label={`Prediction Forecasting Horizon · ${prefs.horizonMonths} mo`}>
            <input
              type="range"
              min={1}
              max={6}
              value={prefs.horizonMonths}
              onChange={(e) => setPrefs({ horizonMonths: +e.target.value })}
              className="w-full accent-data"
            />
          </Field>

          <Field label="Optimization Metric">
            <select
              value={prefs.metric}
              onChange={(e) => setPrefs({ metric: e.target.value as any })}
              className="w-full bg-background border border-border-strong text-xs font-mono py-1.5 px-2 text-foreground focus:outline-none focus:border-data/60"
            >
              <option value="officer-miles">Minimized Officer-Miles</option>
              <option value="uniform">Uniform Regional Distribution</option>
            </select>
          </Field>
        </div>
      )}
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground mb-1.5">{label}</div>
      {children}
    </div>
  );
}
