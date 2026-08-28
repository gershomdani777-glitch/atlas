"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { DecisionReceipt } from "@/lib/types";
import { RegimeBadge } from "@/components/RegimeBadge";

export default function DecisionReceiptPage() {
  const params = useParams<{ id: string }>();
  const [receipt, setReceipt] = useState<DecisionReceipt | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const id = Number(params.id);
    if (!Number.isFinite(id)) return;
    api
      .getDecisionReceipt(id)
      .then(setReceipt)
      .catch(() => setError(true));
  }, [params.id]);

  if (error) {
    return (
      <div style={{ padding: "56px 40px" }}>
        <p>Decision not found.</p>
      </div>
    );
  }

  if (!receipt) {
    return (
      <div style={{ padding: "56px 40px" }}>
        <p style={{ opacity: 0.6 }}>Loading receipt…</p>
      </div>
    );
  }

  const { decision, checks, sizing, inputs_snapshot } = receipt;

  return (
    <div style={{ padding: "56px 40px 80px", maxWidth: 900 }}>
      <span className="eyebrow-label">Receipt #{String(decision.id).padStart(4, "0")}</span>
      <h1
        className="font-grenette text-display animate-entrance"
        style={{
          color: decision.accepted ? "var(--color-deep-forest)" : "var(--color-charcoal)",
          margin: "0 0 24px",
        }}
      >
        {decision.accepted ? "Accepted." : "Rejected."}
      </h1>
      <p style={{ fontSize: 18, margin: "0 0 48px", display: "flex", gap: 10, alignItems: "center" }}>
        {decision.asset} · {decision.direction.toUpperCase()} · <RegimeBadge regime={decision.regime} />
      </p>

      <Block title="Thesis Proposal">
        <p className="body-copy" style={{ fontSize: 16, marginBottom: 16 }}>{decision.thesis}</p>
        <Row label="Expected edge" value={`${decision.expected_edge_bps.toFixed(1)} bps`} />
        <Row label="Confidence" value={decision.confidence.toFixed(2)} />
        <Row label="Reason" value={decision.reason} />
      </Block>

      <Block title="Deterministic Control">
        {Object.entries(checks).map(([key, pass]) => (
          <Row key={key} label={key.replaceAll("_", " ")} value={pass ? "Pass" : "Fail"} tone={pass ? "pass" : "fail"} />
        ))}
      </Block>

      <Block title="Sizing Rationale">
        {Object.entries(sizing).map(([key, value]) => (
          <Row key={key} label={key.replaceAll("_", " ")} value={String(value)} />
        ))}
      </Block>

      <Block title="Market Inputs Used">
        {Object.entries(inputs_snapshot).map(([key, value]) => (
          <Row key={key} label={key.replaceAll("_", " ")} value={String(value)} />
        ))}
      </Block>
    </div>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card-paper" style={{ marginBottom: 24 }}>
      <span className="eyebrow-label">{title}</span>
      <div>{children}</div>
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "pass" | "fail" }) {
  const color = tone === "pass" ? "var(--color-forest-mid)" : tone === "fail" ? "var(--color-charcoal)" : undefined;
  return (
    <div className="data-row" style={{ padding: "10px 0", borderBottom: "1px solid rgba(4, 63, 46, 0.08)" }}>
      <span style={{ textTransform: "capitalize", opacity: 0.7, fontSize: 14 }}>{label}</span>
      <strong style={{ color, fontSize: 14 }}>{value}</strong>
    </div>
  );
}
