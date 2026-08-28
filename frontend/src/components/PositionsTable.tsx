import type { Position } from "@/lib/types";

function money(value: number): string {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
}

export function PositionsTable({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return <p style={{ opacity: 0.6, fontSize: 14 }}>No open positions.</p>;
  }

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Asset</th>
          <th>Side</th>
          <th>Size</th>
          <th>Entry</th>
          <th>Opened</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((p) => (
          <tr key={p.id}>
            <td>{p.asset}</td>
            <td style={{ color: p.side === "long" ? "var(--color-forest-mid)" : "var(--color-charcoal)" }}>
              {p.side.toUpperCase()}
            </td>
            <td>{p.size.toFixed(6)}</td>
            <td>{money(p.entry_price)}</td>
            <td>{new Date(p.opened_at).toLocaleTimeString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
