import type { Decision } from "@/lib/types";

export function DecisionRow({ decision }: { decision: Decision }) {
  return (
    <div className="card-paper data-row">
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <strong style={{ fontFamily: "var(--font-graphik)", fontWeight: 600, fontSize: 16 }}>
            {decision.asset} · {decision.direction.toUpperCase()}
          </strong>
          <span className="tag-badge" data-tone={decision.accepted ? "accent" : "rejected"}>
            {decision.accepted ? "Accepted" : "Rejected"}
          </span>
        </div>
        <p className="body-copy" style={{ fontSize: 14, opacity: 0.75, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {decision.thesis || decision.reason}
        </p>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
        <div>{decision.accepted ? `$${decision.size.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"}</div>
        <div style={{ opacity: 0.6 }}>{decision.confidence.toFixed(2)} conf</div>
      </div>
    </div>
  );
}
