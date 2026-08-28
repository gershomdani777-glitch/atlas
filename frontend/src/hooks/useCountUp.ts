"use client";

import { useEffect, useRef, useState } from "react";

/** Animates a number from its previous value to `target` over `duration` ms.
 * Used for the stat-card figures (equity, P&L, exposure) so updates read as
 * a smooth tick rather than a jarring re-render. */
export function useCountUp(target: number, duration = 600): number {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const from = fromRef.current;
    const delta = target - from;
    if (delta === 0) return;

    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(from + delta * eased);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return value;
}
