"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useLiveSocket, type LiveState } from "@/hooks/useLiveSocket";

const AtlasContext = createContext<LiveState | null>(null);

export function AtlasProvider({ children }: { children: ReactNode }) {
  const live = useLiveSocket();
  return <AtlasContext.Provider value={live}>{children}</AtlasContext.Provider>;
}

export function useAtlas(): LiveState {
  const ctx = useContext(AtlasContext);
  if (!ctx) throw new Error("useAtlas must be used within AtlasProvider");
  return ctx;
}
