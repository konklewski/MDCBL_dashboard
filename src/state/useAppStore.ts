import { create } from "zustand";

export type Mode = "current" | "optimized";
export type Dim = "2d" | "3d";

interface AppState {
  selectedForceName: string | null;
  hoverForceName: string | null;
  mode: Mode;
  dim: Dim;
  sidebarTab: 0 | 1 | 2;
  mapboxToken: string;
  setSelected: (n: string | null) => void;
  setHover: (n: string | null) => void;
  setMode: (m: Mode) => void;
  setDim: (d: Dim) => void;
  setTab: (t: 0 | 1 | 2) => void;
  setToken: (t: string) => void;
}

const DEFAULT_MAPBOX_TOKEN =
  "pk.eyJ1IjoiamtvbmtsZXdza2kiLCJhIjoiY21wNjloYTN3MG5lbTJ3c2E5MXU4YXkycSJ9.-vyo9RLZNXPEyebVGBi_vg";

// SSR-safe: same value on server and client to avoid hydration mismatch.
// localStorage override is applied later via a client-only effect.
const initialToken =
  (import.meta.env.VITE_MAPBOX_TOKEN as string | undefined) || DEFAULT_MAPBOX_TOKEN;

export const useApp = create<AppState>((set) => ({
  selectedForceName: "Metropolitan Police",
  hoverForceName: null,
  mode: "current",
  dim: "2d",
  sidebarTab: 0,
  mapboxToken: initialToken,
  setSelected: (n) => set({ selectedForceName: n }),
  setHover: (n) => set({ hoverForceName: n }),
  setMode: (mode) => set({ mode }),
  setDim: (dim) => set({ dim }),
  setTab: (sidebarTab) => set({ sidebarTab }),
  setToken: (t) => {
    if (typeof window !== "undefined") localStorage.setItem("mapbox_token", t);
    set({ mapboxToken: t });
  },
}));
