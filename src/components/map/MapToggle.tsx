import { useApp } from "@/state/useAppStore";

export function MapToggle() {
  const mode = useApp((s) => s.mode);
  const setMode = useApp((s) => s.setMode);
  return (
    <div className="absolute top-3 right-3 border border-border-strong bg-surface/85 backdrop-blur px-1.5 py-1.5 flex items-center gap-1 font-mono text-[10px] tracking-wider uppercase">
      {(["current", "optimized"] as const).map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          className={
            "px-3 py-1.5 transition-colors " +
            (mode === m
              ? "bg-data/15 text-data border border-data/50"
              : "text-muted-foreground hover:text-foreground border border-transparent")
          }
        >
          {m === "current" ? "Current Allocation" : "Model-Optimized"}
        </button>
      ))}
    </div>
  );
}
