import { useEffect, useMemo, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapboxMap, Marker } from "mapbox-gl";
import { useQuery } from "@tanstack/react-query";
import { useApp } from "@/state/useAppStore";
import {
  fetchForceBoundaries,
  fallbackForceBoundaries,
  normalizeForceName,
  centroid,
  arcLine,
  approximateForceCenter,
} from "@/data/geo";
import { forceByName, forces } from "@/data/forces";
import { originsFor, destinationsFor } from "@/data/transfers";
import { MapToggle } from "./MapToggle";
import { FloatingControls } from "./FloatingControls";
import { TokenGate } from "./TokenGate";

// UK bounding box used for the default "open on UK" view.
const UK_BOUNDS: [[number, number], [number, number]] = [
  [-8.65, 49.75],
  [1.85, 59.55],
];

type MapboxModule = typeof import("mapbox-gl").default;
const PINNED_LABEL_FORCES = new Set(["City of London", "Metropolitan Police"]);

export function ForceMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapboxRef = useRef<MapboxModule | null>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const centroidsRef = useRef<Map<string, [number, number]>>(new Map());
  const [mapStatus, setMapStatus] = useState<"loading" | "ready" | "error">("loading");
  const [mapError, setMapError] = useState<string | null>(null);

  const token = useApp((s) => s.mapboxToken);
  const mode = useApp((s) => s.mode);
  const dim = useApp((s) => s.dim);
  const selectedForceName = useApp((s) => s.selectedForceName);
  const setSelected = useApp((s) => s.setSelected);
  const setHover = useApp((s) => s.setHover);
  const modeRef = useRef(mode);
  const selectedRef = useRef(selectedForceName);

  modeRef.current = mode;
  selectedRef.current = selectedForceName;

  const fallbackGeo = useMemo(() => fallbackForceBoundaries(), []);
  const { data: geo = fallbackGeo } = useQuery({
    queryKey: ["force-boundaries"],
    queryFn: fetchForceBoundaries,
    // Show placeholder rectangles immediately, but keep retrying the real source in
    // the background so a slow first load self-heals instead of sticking on rectangles.
    placeholderData: fallbackGeo,
    staleTime: Infinity,
    retry: 5,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });

  // Precompute per-force flow numbers.
  const flows = useMemo(() => {
    const m = new Map<string, { inflow: number; outflow: number }>();
    for (const f of forces) {
      const inflow = originsFor(f.name).reduce((s, t) => s + t.headcount, 0);
      const outflow = destinationsFor(f.name).reduce((s, t) => s + t.headcount, 0);
      m.set(f.name, { inflow, outflow });
    }
    return m;
  }, []);

  const coordFor = (forceName: string): [number, number] | null => {
    if (PINNED_LABEL_FORCES.has(forceName)) return approximateForceCenter(forceName);
    const coord = centroidsRef.current.get(forceName) ?? approximateForceCenter(forceName);
    if (coord && !centroidsRef.current.has(forceName)) centroidsRef.current.set(forceName, coord);
    return coord;
  };

  const flowFeatureCollectionFor = (forceName: string | null) => {
    const fc = { type: "FeatureCollection" as const, features: [] as any[] };
    if (modeRef.current !== "optimized" || !forceName) return fc;

    const selectedCoord = coordFor(forceName);
    if (!selectedCoord) return fc;

    for (const t of destinationsFor(forceName)) {
      const destination = coordFor(t.destination);
      if (!destination) continue;
      fc.features.push({
        type: "Feature",
        properties: {
          headcount: t.headcount,
          origin: t.origin,
          destination: t.destination,
          direction: "outbound",
          selectedForce: forceName,
        },
        geometry: { type: "LineString", coordinates: arcLine(selectedCoord, destination) },
      });
    }

    for (const t of originsFor(forceName)) {
      const origin = coordFor(t.origin);
      if (!origin) continue;
      fc.features.push({
        type: "Feature",
        properties: {
          headcount: t.headcount,
          origin: t.origin,
          destination: t.destination,
          direction: "inbound",
          selectedForce: forceName,
        },
        geometry: { type: "LineString", coordinates: arcLine(origin, selectedCoord) },
      });
    }

    return fc;
  };

  const ensureArchesLayers = (map: MapboxMap, data: ReturnType<typeof flowFeatureCollectionFor>) => {
    if (!map.getSource("arches")) map.addSource("arches", { type: "geojson", data: data as any });
    // Dark casing rendered underneath the coloured line so the flows read against
    // the green basemap (a colour-on-colour line otherwise disappears over land).
    if (!map.getLayer("arches-glow"))
      map.addLayer({
        id: "arches-glow",
        type: "line",
        source: "arches",
        slot: "top",
        paint: {
          "line-color": "#0b0f14",
          "line-width": ["interpolate", ["linear"], ["get", "headcount"], 1, 3.4, 2000, 7.5],
          "line-opacity": 0.55,
          "line-blur": 0.6,
        },
      });
    if (!map.getLayer("arches-line"))
      map.addLayer({
        id: "arches-line",
        type: "line",
        source: "arches",
        slot: "top",
        paint: {
          // Vivid, high-saturation hues. Semantic preserved: inbound (officers
          // arriving / deficit) = green, outbound (leaving / surplus) = red.
          "line-color": [
            "match",
            ["get", "direction"],
            "outbound",
            "#ff4438",
            "inbound",
            "#10e06a",
            "#36a3ff",
          ],
          "line-width": ["interpolate", ["linear"], ["get", "headcount"], 1, 1.6, 2000, 4],
          "line-opacity": 1,
        },
      });
  };

  const syncFlowLines = (forceName = selectedRef.current) => {
    const map = mapRef.current;
    if (!map) return;

    const data = flowFeatureCollectionFor(forceName);
    containerRef.current?.setAttribute("data-flow-selected", forceName ?? "");
    containerRef.current?.setAttribute("data-flow-count", String(data.features.length));
    if (!map.isStyleLoaded()) {
      map.once("idle", () => syncFlowLines(forceName));
      return;
    }

    if (map.getLayer("arches-line")) map.removeLayer("arches-line");
    if (map.getLayer("arches-glow")) map.removeLayer("arches-glow");
    if (map.getSource("arches")) map.removeSource("arches");
    if (data.features.length > 0) ensureArchesLayers(map, data);
    map.triggerRepaint();
  };

  // Init map
  useEffect(() => {
    if (!token || !containerRef.current || mapRef.current) return;
    let disposed = false;
    let loaded = false;
    let ro: ResizeObserver | null = null;
    let resizeTimer: ReturnType<typeof setTimeout> | null = null;
    setMapStatus("loading");
    setMapError(null);

    const init = async () => {
      const mapboxgl = (await import("mapbox-gl")).default;
      if (disposed || !containerRef.current) return;

      mapboxRef.current = mapboxgl;
      mapboxgl.accessToken = token.trim();
      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/standard",
        center: [-2.65, 54.45],
        zoom: 5.15,
        minZoom: 4.3,
        maxZoom: 12,
        pitch: 0,
        attributionControl: false,
      });
      map.addControl(new mapboxgl.AttributionControl({ compact: true }), "bottom-left");
      mapRef.current = map;

      map.on("style.load", () => {
        try {
          map.setConfigProperty("basemap", "lightPreset", "day");
          map.setConfigProperty("basemap", "showPointOfInterestLabels", false);
          map.setConfigProperty("basemap", "showTransitLabels", false);
          map.setConfigProperty("basemap", "showRoadLabels", false);
        } catch {
          // Older styles do not expose basemap config properties.
        }
        map.fitBounds(UK_BOUNDS, { padding: { top: 64, right: 64, bottom: 64, left: 64 }, duration: 0 });
        map.resize();
      });

      map.once("load", () => {
        loaded = true;
        map.fitBounds(UK_BOUNDS, { padding: { top: 64, right: 64, bottom: 64, left: 64 }, duration: 0 });
        setMapStatus("ready");
      });

      map.on("error", (event) => {
        if (loaded) return;
        const message = event.error?.message ?? "Mapbox failed to load the basemap.";
        console.error("Mapbox error", event.error);
        setMapError(message);
        setMapStatus("error");
      });

      ro = new ResizeObserver(() => map.resize());
      ro.observe(containerRef.current);
      resizeTimer = setTimeout(() => {
        map.resize();
        map.fitBounds(UK_BOUNDS, { padding: { top: 64, right: 64, bottom: 64, left: 64 }, duration: 0 });
      }, 250);
    };

    init().catch((error) => {
      console.error("Mapbox init error", error);
      setMapError(error instanceof Error ? error.message : "Mapbox failed to initialize.");
      setMapStatus("error");
    });

    return () => {
      disposed = true;
      if (resizeTimer) clearTimeout(resizeTimer);
      ro?.disconnect();
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [token]);

  // Pitch toggle
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({ pitch: dim === "3d" ? 55 : 0, bearing: dim === "3d" ? -18 : 0, duration: 800 });
  }, [dim]);

  // Add boundary outline layer when geo + map ready (no fill — keep Mapbox basemap visible)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const ensure = () => {
      const features = geo.features.map((f) => {
        const raw =
          f.properties?.PFA23NM ||
          f.properties?.PFA22NM ||
          f.properties?.PFA20NM ||
          f.properties?.pfa15nm ||
          f.properties?.name ||
          f.properties?.NAME;
        const forceName = normalizeForceName(raw);
        if (forceName && !centroidsRef.current.has(forceName)) {
          centroidsRef.current.set(forceName, approximateForceCenter(forceName) ?? centroid(f.geometry));
        }
        return {
          ...f,
          properties: {
            ...f.properties,
            forceName: forceName ?? "Unknown",
          },
        };
      });
      const fc = { type: "FeatureCollection" as const, features };

      if (map.getSource("forces")) {
        (map.getSource("forces") as GeoJSONSource).setData(fc as any);
      } else {
        map.addSource("forces", { type: "geojson", data: fc as any });
        // Invisible fill purely as a click/hover target.
        map.addLayer({
          id: "forces-fill",
          type: "fill",
          source: "forces",
          slot: "top",
          paint: {
            "fill-color": "#000000",
            "fill-opacity": [
              "case",
              ["==", ["get", "forceName"], selectedForceName ?? ""],
              0.06,
              0.0,
            ],
          },
        });
        map.addLayer({
          id: "forces-line",
          type: "line",
          source: "forces",
          slot: "top",
          paint: {
            "line-color": [
              "case",
              ["==", ["get", "forceName"], selectedForceName ?? ""],
              "#1e4f7a",
              "#18181b",
            ],
            "line-width": [
              "case",
              ["==", ["get", "forceName"], selectedForceName ?? ""],
              3.0,
              1.4,
            ],
            "line-opacity": 0.88,
          },
        });

        map.on("mousemove", "forces-fill", (e) => {
          map.getCanvas().style.cursor = "pointer";
          const f = e.features?.[0];
          if (!f) return;
          setHover(f.properties?.forceName as string);
        });
        map.on("mouseleave", "forces-fill", () => {
          map.getCanvas().style.cursor = "";
          setHover(null);
        });
        map.on("click", "forces-fill", (e) => {
          const f = e.features?.[0];
          const forceName = f?.properties?.forceName as string | undefined;
          if (!forceName) return;
          selectedRef.current = forceName;
          setSelected(forceName);
          syncFlowLines(forceName);
        });
      }
    };

    if (map.isStyleLoaded()) ensure();
    else map.once("style.load", ensure);
  }, [geo, setHover, setSelected, selectedForceName]);

  // Update boundary paint when selection changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("forces-fill")) return;
    map.setPaintProperty("forces-fill", "fill-opacity", [
      "case",
      ["==", ["get", "forceName"], selectedForceName ?? ""],
      0.06,
      0.0,
    ]);
    map.setPaintProperty("forces-line", "line-color", [
      "case",
      ["==", ["get", "forceName"], selectedForceName ?? ""],
      "#1e4f7a",
      "#18181b",
    ]);
    map.setPaintProperty("forces-line", "line-width", [
      "case",
      ["==", ["get", "forceName"], selectedForceName ?? ""],
      3.0,
      1.4,
    ]);
  }, [selectedForceName]);

  // Render / refresh emoji markers per force
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const render = () => {
      const mapboxgl = mapboxRef.current;
      if (!mapboxgl) return;
      if (centroidsRef.current.size === 0) {
        for (const feature of geo.features) {
          const raw =
            feature.properties?.PFA23NM ||
            feature.properties?.PFA22NM ||
            feature.properties?.PFA20NM ||
            feature.properties?.pfa15nm ||
            feature.properties?.name ||
            feature.properties?.NAME;
          const forceName = normalizeForceName(raw);
          if (forceName) centroidsRef.current.set(forceName, approximateForceCenter(forceName) ?? centroid(feature.geometry));
        }
      }
      // Clear existing markers
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      forces.forEach((force) => {
        const forceName = force.name;
        const coord = PINNED_LABEL_FORCES.has(forceName)
          ? approximateForceCenter(forceName)
          : centroidsRef.current.get(forceName) ?? approximateForceCenter(forceName);
        if (!coord) return;
        if (!centroidsRef.current.has(forceName)) centroidsRef.current.set(forceName, coord);
        const flow = flows.get(forceName) ?? { inflow: 0, outflow: 0 };
        const fte = force.baselineFTE;

        const el = document.createElement("div");
        el.className = "force-badge";
        el.dataset.forceName = forceName;
        el.style.cursor = "pointer";
        const selected = forceName === selectedForceName;
        const deltaHtml =
          mode === "optimized"
            ? `<div class="badge-deltas">
                 ${flow.outflow > 0 ? `<span class="delta out">−${formatNum(flow.outflow)}</span>` : ""}
                 ${flow.inflow > 0 ? `<span class="delta in">+${formatNum(flow.inflow)}</span>` : ""}
               </div>`
            : "";
        el.innerHTML = `
          <div class="badge-shell ${selected ? "is-selected" : ""}">
            <div class="badge-main">
              <span class="badge-emoji">👮</span>
              <span class="badge-count">${formatNum(fte)}</span>
            </div>
            ${deltaHtml}
          </div>
        `;
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          selectedRef.current = forceName;
          setSelected(forceName);
          syncFlowLines(forceName);
        });
        const marker = new mapboxgl.Marker({ element: el, anchor: "center" })
          .setLngLat(coord)
          .addTo(map);
        markersRef.current.push(marker);
      });
    };

    if (map.isStyleLoaded()) render();
    else map.once("idle", render);
  }, [geo, mode, selectedForceName, flows, setSelected]);

  // Render arches in optimized + selected
  useEffect(() => {
    syncFlowLines(selectedForceName);
  }, [mode, selectedForceName, geo]);

  if (!token) return <TokenGate />;

  return (
    <div className="relative h-full w-full bg-background">
      <div ref={containerRef} className="force-map-canvas absolute inset-0" />
      {mapStatus !== "ready" && (
        <div className="absolute inset-0 z-10 grid place-items-center bg-background/70 backdrop-blur-[1px]">
          <div className="max-w-md border border-border-strong bg-surface/95 px-4 py-3 shadow-xl">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {mapStatus === "error" ? "Mapbox Load Error" : "Loading UK Map"}
            </div>
            <div className="mt-1 text-sm text-foreground">
              {mapStatus === "error"
                ? mapError ?? "The Mapbox basemap could not be initialized."
                : "Initializing Mapbox Standard with UK police force boundaries."}
            </div>
          </div>
        </div>
      )}
      <MapToggle />
      <FloatingControls />
      <div className="absolute top-3 left-3 pointer-events-none">
        <div className="border border-border-strong bg-surface/85 backdrop-blur px-2.5 py-1.5">
          <div className="text-[9px] font-mono tracking-[0.18em] uppercase text-muted-foreground">
            Theatre View · {forces.length} Computed Forces
          </div>
        </div>
      </div>
      <Legend />
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 10000) return `${(n / 1000).toFixed(1)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toString();
}

function Legend() {
  const mode = useApp((s) => s.mode);
  return (
    <div className="absolute bottom-3 left-3 border border-border-strong bg-surface/85 backdrop-blur px-3 py-2 font-mono text-[10px] tracking-wider uppercase">
      <div className="text-muted-foreground mb-1.5">Legend</div>
      {mode === "optimized" ? (
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-2"><span>👮</span> Current FTE</span>
          <span className="flex items-center gap-2"><span className="text-deficit">−x</span> Officers re-allocated out</span>
          <span className="flex items-center gap-2"><span className="text-surplus">+y</span> Officers arriving</span>
          <span className="flex items-center gap-2"><span className="h-px w-5 bg-deficit" /> Selected force outbound flow</span>
          <span className="flex items-center gap-2"><span className="h-px w-5 bg-surplus" /> Selected force inbound flow</span>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-2"><span>👮</span> Baseline FTE per force</span>
        </div>
      )}
    </div>
  );
}
