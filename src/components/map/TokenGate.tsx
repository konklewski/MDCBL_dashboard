import { useApp } from "@/state/useAppStore";
import { useState } from "react";

export function TokenGate() {
  const setToken = useApp((s) => s.setToken);
  const [v, setV] = useState("");
  return (
    <div className="relative h-full w-full grid place-items-center bg-background">
      <div className="pointer-events-none absolute inset-0 scanlines" />
      <div className="relative w-[420px] max-w-[90vw] border border-border-strong bg-surface p-6">
        <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-data mb-2">
          Mapbox Access · Required
        </div>
        <h2 className="text-base text-foreground mb-2">Provide your Mapbox public token</h2>
        <p className="text-xs text-muted-foreground mb-4 leading-relaxed">
          Paste your <code className="text-data font-mono">pk.*</code> token to initialize the geospatial canvas.
          It is stored locally in your browser only.
        </p>
        <input
          type="text"
          autoFocus
          value={v}
          onChange={(e) => setV(e.target.value)}
          placeholder="pk.eyJ…"
          className="w-full bg-background border border-border-strong px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:border-data/60 mb-3"
        />
        <button
          onClick={() => v.trim().startsWith("pk.") && setToken(v.trim())}
          className="w-full bg-data text-primary-foreground font-mono text-[11px] tracking-wider uppercase py-2 hover:bg-data/90 disabled:opacity-40"
          disabled={!v.trim().startsWith("pk.")}
        >
          Initialize Map
        </button>
      </div>
    </div>
  );
}
