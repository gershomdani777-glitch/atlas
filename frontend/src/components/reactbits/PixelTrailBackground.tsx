"use client";

import dynamic from "next/dynamic";

// PixelTrail uses @react-three/fiber (WebGL canvas), which can't render on
// the server. Scoped to a single dynamic import so it can never block or
// slow down the data-heavy pages (Decisions/Receipt/Risk/Performance).
const PixelTrail = dynamic(() => import("./PixelTrail"), { ssr: false });

export function PixelTrailBackground({ color = "#043f2e" }: { color?: string }) {
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "auto" }}>
      <PixelTrail
        gridSize={44}
        trailSize={0.12}
        maxAge={300}
        interpolate={6}
        color={color}
        gooeyFilter={{ id: "atlas-hero-goo", strength: 3 }}
      />
    </div>
  );
}
