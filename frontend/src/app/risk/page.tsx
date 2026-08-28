"use client";

import { RiskConfigForm } from "@/components/RiskConfigForm";
import { KillSwitch } from "@/components/KillSwitch";
import { useAtlas } from "@/context/AtlasProvider";

export default function RiskConsolePage() {
  const { running } = useAtlas();

  return (
    <div style={{ padding: "56px 40px 80px" }}>
      <span className="eyebrow-label">Risk Console</span>
      <h1 className="font-grenette text-heading-lg" style={{ color: "var(--color-deep-forest)", margin: "0 0 24px" }}>
        Capital control.
      </h1>
      <p className="body-copy" style={{ marginBottom: 40, opacity: 0.85 }}>
        Live-editable constraints enforced pre-trade by the deterministic risk engine. Changes apply on the next cycle.
        Agent is currently <strong>{running ? "running" : "halted"}</strong>.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 24, alignItems: "flex-start" }}>
        <div className="card-paper">
          <RiskConfigForm />
        </div>
        <div className="card-forest" style={{ display: "flex", flexDirection: "column", gap: 16, alignItems: "center", minWidth: 200 }}>
          <span className="eyebrow-label" data-tone="on-dark">Emergency</span>
          <KillSwitch />
        </div>
      </div>
    </div>
  );
}
