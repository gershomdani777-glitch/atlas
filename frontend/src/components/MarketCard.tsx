"use client";

import PixelSwap from "@/components/reactbits/PixelSwap";
import { RegimeBadge } from "@/components/RegimeBadge";
import type { MarketAsset } from "@/lib/types";

function money(value: number): string {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: value < 10 ? 4 : 0 })}`;
}

// Front face: at-a-glance price + regime. Hovering pixel-dissolves into a
// forest-dark detail face (volatility/liquidity/depth/trend) — a genuine
// progressive-disclosure pattern for a market table, not decoration.
export function MarketCard({ asset }: { asset: MarketAsset }) {
  return (
    <PixelSwap
      className="cursor-target"
      style={{ borderRadius: "var(--radius-lg)", opacity: asset.stale ? 0.5 : 1 }}
      aspectRatio="4 / 3"
      trigger="hover"
      pixelSize={22}
      pixelDuration={260}
      duration={620}
      pattern="center"
      pixelRadius={20}
      firstContent={
        <div className="card-paper" style={{ height: "100%", boxSizing: "border-box", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <span className="eyebrow-label">{asset.symbol.toUpperCase()}</span>
          <div>
            <p className="font-graphik" style={{ fontSize: 26, fontWeight: 500, margin: "0 0 8px" }}>
              {money(asset.price)}
            </p>
            <RegimeBadge regime={asset.regime} />
          </div>
        </div>
      }
      secondContent={
        <div className="card-forest" style={{ height: "100%", boxSizing: "border-box", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <span className="eyebrow-label" data-tone="on-dark">
            {asset.symbol.toUpperCase()} detail
          </span>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <StatLine label="Volatility" value={asset.volatility.toFixed(4)} />
            <StatLine label="Liquidity" value={asset.liquidity.toFixed(2)} />
            <StatLine label="Depth" value={money(asset.depth)} />
            <StatLine label="Trend" value={asset.trend.toFixed(2)} />
          </div>
        </div>
      }
    />
  );
}

function StatLine({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
      <span style={{ opacity: 0.75 }}>{label}</span>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{value}</strong>
    </div>
  );
}
