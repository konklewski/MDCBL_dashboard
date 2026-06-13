import { useApp } from "@/state/useAppStore";
import { Box, Square } from "lucide-react";

export function FloatingControls() {
  const dim = useApp((s) => s.dim);
  const setDim = useApp((s) => s.setDim);

  return (
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
    </div>
  );
}
