"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Decision } from "@/lib/types";
import { useAtlas } from "@/context/AtlasProvider";
import { DecisionRow } from "@/components/DecisionRow";
import AnimatedList from "@/components/reactbits/AnimatedList";

export default function DecisionsPage() {
  const router = useRouter();
  const { recentDecisions } = useAtlas();
  const [initial, setInitial] = useState<Decision[]>([]);

  useEffect(() => {
    api.getDecisions({ limit: 40 }).then(setInitial).catch(() => {});
  }, []);

  const merged = useMemo(() => {
    const byId = new Map<number, Decision>();
    for (const d of initial) byId.set(d.id, d);
    for (const d of recentDecisions) byId.set(d.id, d);
    return Array.from(byId.values()).sort((a, b) => b.id - a.id);
  }, [initial, recentDecisions]);

  return (
    <div style={{ padding: "56px 40px 80px" }}>
      <span className="eyebrow-label">Audit Trail</span>
      <h1 className="font-grenette text-heading-lg" style={{ color: "var(--color-deep-forest)", margin: "0 0 40px" }}>
        Decision feed.
      </h1>

      <AnimatedList
        items={merged}
        onItemSelect={(item) => router.push(`/decisions/${(item as Decision).id}`)}
        renderItem={(item) => <DecisionRow decision={item as Decision} />}
        displayScrollbar={false}
      />
      {merged.length === 0 && <p style={{ opacity: 0.6 }}>Waiting for the first cycle…</p>}
    </div>
  );
}
