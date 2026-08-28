"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { MarketAsset } from "@/lib/types";
import { useAtlas } from "@/context/AtlasProvider";
import { useCountUp } from "@/hooks/useCountUp";
import { MarketCard } from "@/components/MarketCard";
import { PositionsTable } from "@/components/PositionsTable";
import { PixelTrailBackground } from "@/components/reactbits/PixelTrailBackground";
import SplitFlapText from "@/components/reactbits/SplitFlapText";
import GooeyNav from "@/components/reactbits/GooeyNav";

function money(value: number): string {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

const CONSOLE_SECTIONS = [
  { label: "Live Ops", href: "/" },
  { label: "Decisions", href: "/decisions" },
  { label: "Performance", href: "/performance" },
  { label: "Risk Console", href: "/risk" },
];

export default function LiveOpsPage() {
  const live = useAtlas();
  const [market, setMarket] = useState<MarketAsset[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const rows = await api.getMarket();
        if (!cancelled) setMarket(rows);
      } catch {
        // backend not reachable yet; live socket will still try to connect
      }
    }
    load();
    const interval = setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const mergedMarket = useMemo(
    () =>
      market.map((asset) => ({
        ...asset,
        price: live.prices[asset.symbol] ?? asset.price,
        regime: live.regimes[asset.symbol] ?? asset.regime,
      })),
    [market, live.prices, live.regimes]
  );

  const tickerWords = useMemo(() => {
    if (mergedMarket.length === 0) return ["ATLAS ONLINE"];
    return mergedMarket.map((a) => `${a.symbol} ${money(a.price)} ${a.regime.toUpperCase()}`);
  }, [mergedMarket]);

  const equity = useCountUp(live.equity);
  const peakEquity = useCountUp(live.peakEquity);
  const pnl = useCountUp(live.equity - live.capital);
  const exposure = useCountUp(live.positions.reduce((sum, p) => sum + p.size * p.entry_price, 0));

  return (
    <div style={{ padding: "0 40px" }}>
      {/* Hero */}
      <section style={{ position: "relative", minHeight: 480, display: "flex", alignItems: "center", overflow: "hidden", padding: "80px 0", borderRadius: "var(--radius-lg)" }}>
        <PixelTrailBackground color="#2a6f2b" />
        <div style={{ position: "relative", zIndex: 2, maxWidth: 720 }}>
          <span className="eyebrow-label">Autonomous Decision Loop</span>
          <h1 className="font-grenette text-display" style={{ color: "var(--color-deep-forest)", margin: 0 }}>
            Decision control, live.
          </h1>
          <p className="body-copy" style={{ marginTop: 20 }}>
            Cycle {live.cycle} · {live.running ? "running" : "halted"}. Claude proposes, the risk engine disposes.
          </p>
          <div style={{ marginTop: 32 }}>
            <SplitFlapText
              words={tickerWords}
              tileColor="#043f2e"
              textColor="#fcfcfc"
              fontSize={20}
              gap={4}
              tileRadius={4}
              flipDuration={0.1}
              cycleDelay={2600}
              padTo={26}
            />
          </div>
        </div>
      </section>

      {/* Console navigator */}
      <section style={{ padding: "56px 0 0" }}>
        <span className="eyebrow-label">Explore the Console</span>
        <div className="card-forest" style={{ display: "flex", justifyContent: "center", padding: 24 }}>
          <GooeyNav items={CONSOLE_SECTIONS} particleCount={15} particleDistances={[90, 10]} particleR={100} animationTime={600} timeVariance={300} />
        </div>
      </section>

      {/* Forest stat cards */}
      <section style={{ padding: "56px 0 0" }}>
        <span className="eyebrow-label">Portfolio</span>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
          <StatCard label="Equity" value={money(equity)} sub={`${pnl >= 0 ? "+" : ""}${money(pnl)}`} />
          <StatCard label="Open Exposure" value={money(exposure)} sub={`${live.positions.length} positions`} />
          <StatCard label="Peak Equity" value={money(peakEquity)} sub="high-water mark" />
          <StatCard label="Cycle" value={String(live.cycle)} sub={live.running ? "running" : "halted"} />
        </div>
      </section>

      <section style={{ padding: "56px 0 0" }}>
        <span className="eyebrow-label">Market Overview</span>
        <p className="body-copy" style={{ marginBottom: 20, opacity: 0.8 }}>
          Hover a market to reveal its live volatility, liquidity, depth, and trend.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
          {mergedMarket.map((asset) => (
            <MarketCard key={asset.symbol} asset={asset} />
          ))}
          {mergedMarket.length === 0 && <p style={{ opacity: 0.5 }}>Waiting for market data…</p>}
        </div>
      </section>

      <section style={{ padding: "56px 0 80px" }}>
        <div className="card-paper">
          <span className="eyebrow-label">Positions</span>
          <PositionsTable positions={live.positions} />
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="card-forest animate-entrance">
      <span className="eyebrow-label" data-tone="on-dark">{label}</span>
      <p className="font-graphik" style={{ fontSize: 36, fontWeight: 400, margin: "4px 0", fontVariantNumeric: "tabular-nums" }}>{value}</p>
      <p style={{ fontSize: 13, opacity: 0.7, margin: 0 }}>{sub}</p>
    </div>
  );
}
