import { useState } from "react";
import { fmtE } from "../lib/format";
import { fmtM } from "../lib/finance";

/** Histogramme mensuel recettes (+ coûts) — repris de la maquette. */
export function MonthBars({
  months,
  current,
  selected,
  onSelect,
  showCost,
}: {
  months: { month: string; revenue: number; cost: number }[];
  current: string;
  selected?: string;
  onSelect?: (m: string) => void;
  showCost: boolean;
}) {
  const max = Math.max(1, ...months.map((m) => Math.max(m.revenue, m.cost)));
  return (
    <>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${months.length},1fr)`,
          gap: 8,
          alignItems: "end",
          height: 150,
          marginBottom: 8,
        }}
      >
        {months.map((m) => (
          <div
            key={m.month}
            role={onSelect ? "button" : undefined}
            onClick={() => onSelect?.(m.month)}
            title={`${fmtM(m.month)} : ${fmtE(m.revenue)}${showCost ? ` / coûts ${fmtE(m.cost)}` : ""}`}
            style={{
              display: "flex",
              gap: 3,
              alignItems: "end",
              height: "100%",
              justifyContent: "center",
              cursor: onSelect ? "pointer" : undefined,
            }}
          >
            <i
              style={{
                width: showCost ? "40%" : "60%",
                height: `${(m.revenue / max) * 100}%`,
                minHeight: 2,
                borderRadius: "6px 6px 0 0",
                background: m.month === (selected ?? current) ? "var(--neon)" : "var(--grad)",
              }}
            />
            {showCost && (
              <i
                style={{
                  width: "40%",
                  height: `${(m.cost / max) * 100}%`,
                  minHeight: 2,
                  borderRadius: "6px 6px 0 0",
                  background: "var(--rose)",
                  opacity: 0.6,
                }}
              />
            )}
          </div>
        ))}
      </div>
      <div
        className="hint"
        style={{ display: "grid", gridTemplateColumns: `repeat(${months.length},1fr)`, gap: 8, textAlign: "center" }}
      >
        {months.map((m) => (
          <div key={m.month} style={m.month === current ? { color: "#fff", fontWeight: 700 } : undefined}>
            {fmtM(m.month)}
          </div>
        ))}
      </div>
    </>
  );
}

/** Champ numérique qui enregistre à la sortie du champ (comme les `fin-in` de la maquette). */
export function NumberInput({
  value,
  onCommit,
  width = 90,
  step,
  label,
}: {
  value: string | number | null;
  onCommit: (v: string) => void;
  width?: number;
  step?: string;
  label: string;
}) {
  const [v, setV] = useState(String(value ?? ""));
  const [initial, setInitial] = useState(String(value ?? ""));
  if (String(value ?? "") !== initial) {
    setInitial(String(value ?? ""));
    setV(String(value ?? ""));
  }
  return (
    <input
      className="fin-in"
      type="number"
      step={step}
      style={{ width }}
      aria-label={label}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v !== initial && onCommit(v)}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

export function Legend({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span>
      <i style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: color }} /> {children}
    </span>
  );
}
