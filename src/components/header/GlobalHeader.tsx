import { useApp } from "@/state/useAppStore";
import { forces } from "@/data/forces";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";

export function GlobalHeader() {
  const setSelected = useApp((s) => s.setSelected);
  const [q, setQ] = useState("");

  const results = useMemo(() => {
    if (!q.trim()) return [];
    const t = q.toLowerCase();
    return forces.filter((f) => f.name.toLowerCase().includes(t) || f.code.toLowerCase().includes(t)).slice(0, 6);
  }, [q]);

  return (
    <header className="relative z-30 flex items-center justify-between gap-6 border-b border-border-strong bg-surface/95 px-5 py-3 backdrop-blur">
      <div className="flex items-center gap-3 min-w-0">
        <div className="h-7 w-7 grid place-items-center border border-data/60 bg-data/10">
          <span className="live-dot block h-2 w-2 bg-data" />
        </div>
        <div className="min-w-0">
          <h1 className="font-mono text-[11px] tracking-[0.18em] text-foreground uppercase truncate">
            UK Police Service · Geospatial Resource Reallocation Engine
          </h1>
          <p className="font-mono text-[10px] tracking-wider text-muted-foreground uppercase truncate">
            Phase 3 &amp; Phase 4 Optimization Pipeline Dashboard
          </p>
        </div>
      </div>

      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search territory name or system code…"
          className="w-full bg-background/70 border border-border-strong rounded-sm pl-9 pr-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-data/60"
        />
        {results.length > 0 && (
          <div className="absolute left-0 right-0 top-full mt-1 border border-border-strong bg-surface shadow-2xl z-40">
            {results.map((r) => (
              <button
                key={r.id}
                onClick={() => {
                  setSelected(r.name);
                  setQ("");
                }}
                className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-surface-2 border-b border-border last:border-b-0"
              >
                <span className="text-xs text-foreground truncate">{r.name}</span>
                <span className="font-mono text-[10px] text-data ml-3">{r.code}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden md:flex items-center gap-2 text-[10px] font-mono tracking-wider text-muted-foreground uppercase">
          <span className="h-1.5 w-1.5 rounded-full bg-surplus" />
          System Online
        </div>
      </div>
    </header>
  );
}
