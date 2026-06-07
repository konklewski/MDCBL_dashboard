import { createFileRoute } from "@tanstack/react-router";
import { GlobalHeader } from "@/components/header/GlobalHeader";
import { ForceMap } from "@/components/map/ForceMap";
import { Sidebar } from "@/components/sidebar/Sidebar";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "UK Police Geospatial Resource Reallocation Engine" },
      { name: "description", content: "Phase 3 & Phase 4 optimization pipeline dashboard for UK Territorial Police Forces." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="dark h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
      <GlobalHeader />
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_460px] min-h-0">
        <div className="relative min-h-0 border-r border-border-strong">
          <ForceMap />
        </div>
        <div className="min-h-0 hidden lg:block">
          <Sidebar />
        </div>
      </div>
    </div>
  );
}
