import type { Decision } from "@/lib/types";

export function DecisionRow({ decision }: { decision: Decision }) {
  // Defensive: render a degraded row instead of crashing the whole list if a
  // payload is ever missing a field (a WS event and a REST row have burned
  // us here before by silently diverging in shape).
  const direction = decision.direction ?? "no_action";
  const size = decision.size ?? 0;
  const confidence = decision.confidence ?? 0;

  return (
    <div className="card-paper data-row cursor-target">
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <strong style={{ fontFamily: "var(--font-graphik)", fontWeight: 600, fontSize: 16 }}>
            {decision.asset ?? "?"} · {direction.toUpperCase()}
          </strong>
          <span className="tag-badge" data-tone={decision.accepted ? "accent" : "rejected"}>
            {decision.accepted ? "Accepted" : "Rejected"}
          </span>
        </div>
        <p className="body-copy" style={{ fontSize: 14, opacity: 0.75, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {decision.thesis || decision.reason || "—"}
        </p>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
        <div>{decision.accepted ? `$${size.toLocaleString("en-US", { maximumFractionDigits: 0 })}` : "—"}</div>
        <div style={{ opacity: 0.6 }}>{confidence.toFixed(2)} conf</div>
      </div>
    </div>
  );
}
