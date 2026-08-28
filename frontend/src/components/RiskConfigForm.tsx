"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RiskConfig } from "@/lib/types";
import ClickSpark from "@/components/reactbits/ClickSpark";

const FIELDS: { key: keyof RiskConfig; label: string; step: number }[] = [
  { key: "max_position_pct", label: "Max position % of capital", step: 0.01 },
  { key: "max_exposure_pct", label: "Max total portfolio exposure", step: 0.01 },
  { key: "max_asset_exposure_pct", label: "Max exposure per asset", step: 0.01 },
  { key: "drawdown_stop_pct", label: "Drawdown circuit breaker", step: 0.01 },
  { key: "kelly_fraction", label: "Kelly fraction", step: 0.05 },
  { key: "min_edge_over_cost_bps", label: "Min edge over cost (bps)", step: 1 },
];

export function RiskConfigForm() {
  const [config, setConfig] = useState<RiskConfig | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getRiskConfig().then(setConfig).catch(() => {});
  }, []);

  if (!config) return <p style={{ opacity: 0.6 }}>Loading constraints…</p>;

  async function save() {
    if (!config) return;
    setSaved(false);
    const updated = await api.putRiskConfig(config);
    setConfig(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, maxWidth: 480 }}>
      <span className="eyebrow-label">Constraints</span>
      {FIELDS.map((field) => (
        <label key={field.key} style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 14 }}>
          <span style={{ fontWeight: 500 }}>{field.label}</span>
          <input
            type="number"
            step={field.step}
            value={config[field.key]}
            onChange={(e) => setConfig({ ...config, [field.key]: Number(e.target.value) })}
            style={{
              padding: "10px 14px",
              border: "1px solid rgba(4, 63, 46, 0.2)",
              borderRadius: "var(--radius-sm)",
              fontFamily: "var(--font-graphik)",
              fontSize: 16,
              background: "var(--color-paper-white)",
              color: "var(--color-deep-forest)",
            }}
          />
        </label>
      ))}

      <div style={{ alignSelf: "flex-start", marginTop: 8 }}>
        <ClickSpark sparkColor="#c8f169" sparkCount={10} sparkRadius={22} duration={450}>
          <button className="btn-filled" onClick={save}>
            {saved ? "Saved" : "Save constraints"}
          </button>
        </ClickSpark>
      </div>
    </div>
  );
}
