import type { Regime } from "@/lib/types";

const LABELS: Record<Regime, string> = {
  trending: "Trending",
  mean_reverting: "Mean Reverting",
  high_volatility: "High Volatility",
  illiquid: "Illiquid",
  normal: "Normal",
};

// Chartreuse stays the singular chromatic accent, reserved for the regime
// that most needs attention (trending = active opportunity); everything
// else stays neutral per the "one accent per viewport" rule.
export function RegimeBadge({ regime }: { regime: Regime }) {
  const tone = regime === "trending" ? "accent" : regime === "illiquid" ? "rejected" : undefined;
  return (
    <span className="tag-badge" data-tone={tone}>
      {LABELS[regime] ?? regime}
    </span>
  );
}
