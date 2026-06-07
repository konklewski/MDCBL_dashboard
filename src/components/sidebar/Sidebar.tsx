import { useApp } from "@/state/useAppStore";
import { forceByName } from "@/data/forces";
import { PageOverview } from "./PageOverview";
import { PageDemand } from "./PageDemand";
import { PagePolicy } from "./PagePolicy";

const TABS = ["Overview", "Demand", "Policy"] as const;

export function Sidebar() {
  const name = useApp((s) => s.selectedForceName);
  const tab = useApp((s) => s.sidebarTab);
  const setTab = useApp((s) => s.setTab);
  const force = name ? forceByName.get(name) : null;

  return (
    <aside className="h-full w-full flex flex-col bg-surface border-l border-border-strong">
      <div className="border-b border-border-strong px-4 pt-3 pb-2">
        <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-muted-foreground">
          Active Territory
        </div>
        <div className="mt-1 flex items-center justify-between gap-3">
          <h2 className="text-sm text-foreground truncate">
            {force ? force.name : "No force selected"}
          </h2>
          {force && (
            <span className="font-mono text-[10px] text-data border border-data/40 px-1.5 py-0.5 shrink-0">
              {force.id}
            </span>
          )}
        </div>
        <div className="mt-3 flex gap-0 border border-border-strong">
          {TABS.map((t, i) => (
            <button
              key={t}
              onClick={() => setTab(i as 0 | 1 | 2)}
              className={
                "flex-1 py-1.5 font-mono text-[10px] tracking-wider uppercase " +
                (tab === i ? "bg-data/15 text-data" : "text-muted-foreground hover:text-foreground")
              }
            >
              {`0${i + 1} · ${t}`}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {!force ? (
          <div className="p-6 text-xs text-muted-foreground">Select a force on the map to view diagnostics.</div>
        ) : tab === 0 ? (
          <PageOverview force={force} />
        ) : tab === 1 ? (
          <PageDemand force={force} />
        ) : (
          <PagePolicy force={force} />
        )}
      </div>
    </aside>
  );
}
