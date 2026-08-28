"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import type { Metrics } from "@/lib/types";
import { useCountUp } from "@/hooks/useCountUp";

// Validated against the dataviz skill's checks (see conversation): chartreuse
// fails the categorical lightness/chroma bands and only clears contrast on a
// dark surface, so it's used here as a single accent (meter fill, on
// card-forest) — never as one of several competing line colors. Deep-forest
// and forest-mid are the two sequential-hue steps used for single-series
// trend lines; both clear 3:1+ contrast on the paper-white card surface.
const CHARTREUSE = "#c8f169";
const FOREST = "#043f2e";
const FOREST_MID = "#2a6f2b";
const GRID = "rgba(4, 63, 46, 0.12)";
const CARD_SURFACE = "#fcfcfc";

export default function PerformancePage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getMetrics();
        if (!cancelled) setMetrics(data);
      } catch {
        // ignore, will retry on next interval
      }
    }
    load();
    const interval = setInterval(load, 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const equityData = metrics?.equity_history ?? [];
  const latest = equityData[equityData.length - 1];
  const pnl = useCountUp(latest ? latest.equity - latest.capital : 0);

  const accepted = metrics?.accepted ?? 0;
  const rejected = metrics?.rejected ?? 0;
  const totalDecisions = accepted + rejected;
  const acceptanceRate = useCountUp(totalDecisions > 0 ? (accepted / totalDecisions) * 100 : 0);

  // One aggregated trend line (avg throttle multiplier per cycle, across every
  // active bucket) — the adaptation story ("is risk sizing loosening or
  // tightening over time") in a single validated hue, not four eyeballed ones.
  const throttleTrend = useMemo(() => {
    if (!metrics) return [];
    const byCycle = new Map<number, { sum: number; count: number }>();
    for (const point of metrics.throttle_history) {
      const entry = byCycle.get(point.cycle) ?? { sum: 0, count: 0 };
      entry.sum += point.multiplier;
      entry.count += 1;
      byCycle.set(point.cycle, entry);
    }
    return Array.from(byCycle.entries())
      .sort(([a], [b]) => a - b)
      .map(([cycle, { sum, count }]) => ({ cycle, avg_multiplier: sum / count }));
  }, [metrics]);

  // The table-view twin for the trend line above — per-bucket detail that a
  // single aggregated line necessarily hides, without inventing an unsafe
  // 4+ hue categorical palette to show it on the chart itself.
  const throttleBuckets = useMemo(() => {
    if (!metrics) return [];
    const latestByBucket = new Map<string, { asset: string; thesis_type: string; regime: string; multiplier: number; cycle: number }>();
    for (const point of metrics.throttle_history) {
      const key = `${point.asset} ${point.thesis_type} ${point.regime}`;
      const existing = latestByBucket.get(key);
      if (!existing || point.cycle > existing.cycle) {
        latestByBucket.set(key, point);
      }
    }
    return Array.from(latestByBucket.values()).sort((a, b) => b.cycle - a.cycle);
  }, [metrics]);

  return (
    <div style={{ padding: "56px 40px 80px" }}>
      <span className="eyebrow-label">Adaptation</span>
      <h1 className="font-grenette text-heading-lg" style={{ color: "var(--color-deep-forest)", margin: "0 0 24px" }}>
        Paper P&amp;L.
      </h1>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 40 }}>
        <div className="card-forest" style={{ minWidth: 220 }}>
          <span className="eyebrow-label" data-tone="on-dark">Cumulative</span>
          <p className="font-graphik" style={{ fontSize: 46, fontWeight: 400, margin: 0 }}>
            {pnl >= 0 ? "+" : ""}${pnl.toLocaleString("en-US", { maximumFractionDigits: 2 })}
          </p>
        </div>

        <AcceptanceMeter rate={acceptanceRate} accepted={accepted} rejected={rejected} />
      </div>

      <ChartCard title="Equity curve">
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={equityData}>
            <defs>
              <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={FOREST} stopOpacity={0.1} />
                <stop offset="95%" stopColor={FOREST} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="cycle" tick={{ fontSize: 12, fill: FOREST }} axisLine={{ stroke: GRID }} />
            <YAxis tick={{ fontSize: 12, fill: FOREST }} domain={["auto", "auto"]} axisLine={{ stroke: GRID }} />
            <Tooltip contentStyle={{ background: CARD_SURFACE, border: "1px solid rgba(4,63,46,0.1)", borderRadius: 8 }} />
            <Area type="monotone" dataKey="equity" stroke={FOREST} fill="url(#equityFill)" strokeWidth={2} isAnimationActive />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Drawdown %">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={equityData}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="cycle" tick={{ fontSize: 12, fill: FOREST }} axisLine={{ stroke: GRID }} />
            <YAxis tick={{ fontSize: 12, fill: FOREST }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} axisLine={{ stroke: GRID }} />
            <Tooltip formatter={(v: number) => `${(v * 100).toFixed(2)}%`} contentStyle={{ background: CARD_SURFACE, border: "1px solid rgba(4,63,46,0.1)", borderRadius: 8 }} />
            <Area type="monotone" dataKey="drawdown_pct" stroke={FOREST_MID} fill={FOREST_MID} fillOpacity={0.1} strokeWidth={2} isAnimationActive />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Regime throttle — average multiplier over time">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={throttleTrend}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="cycle" tick={{ fontSize: 12, fill: FOREST }} axisLine={{ stroke: GRID }} />
            <YAxis tick={{ fontSize: 12, fill: FOREST }} domain={[0, "auto"]} axisLine={{ stroke: GRID }} />
            <Tooltip contentStyle={{ background: CARD_SURFACE, border: "1px solid rgba(4,63,46,0.1)", borderRadius: 8 }} />
            <Line type="monotone" dataKey="avg_multiplier" stroke={FOREST} dot={false} strokeWidth={2} isAnimationActive />
          </LineChart>
        </ResponsiveContainer>
        {throttleTrend.length === 0 && <p style={{ opacity: 0.5, fontSize: 14 }}>No throttle history yet.</p>}

        {throttleBuckets.length > 0 && (
          <table className="data-table" style={{ marginTop: 20 }}>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Direction</th>
                <th>Regime</th>
                <th>Multiplier</th>
              </tr>
            </thead>
            <tbody>
              {throttleBuckets.map((b) => (
                <tr key={`${b.asset}-${b.thesis_type}-${b.regime}`}>
                  <td>{b.asset.toUpperCase()}</td>
                  <td>{b.thesis_type}</td>
                  <td>{b.regime.replaceAll("_", " ")}</td>
                  <td>{b.multiplier.toFixed(2)}x</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </ChartCard>
    </div>
  );
}

function AcceptanceMeter({ rate, accepted, rejected }: { rate: number; accepted: number; rejected: number }) {
  const data = [{ value: rate, fill: CHARTREUSE }];
  return (
    <div className="card-forest" style={{ minWidth: 220, display: "flex", flexDirection: "column", alignItems: "center" }}>
      <span className="eyebrow-label" data-tone="on-dark" style={{ alignSelf: "flex-start" }}>Acceptance Rate</span>
      <div style={{ position: "relative", width: 140, height: 140 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            data={data}
            innerRadius="72%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            barSize={14}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar dataKey="value" cornerRadius={7} background={{ fill: "rgba(200, 241, 105, 0.18)" }} isAnimationActive />
          </RadialBarChart>
        </ResponsiveContainer>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span className="font-graphik" style={{ fontSize: 28, fontWeight: 500 }}>{Math.round(rate)}%</span>
        </div>
      </div>
      <p style={{ fontSize: 13, opacity: 0.7, margin: "8px 0 0" }}>{accepted} accepted · {rejected} rejected</p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card-paper" style={{ marginBottom: 24 }}>
      <span className="eyebrow-label">{title}</span>
      {children}
    </div>
  );
}
