"use client";

export type ShapContribution = {
  feature: string;
  value: number | string | null;
  contribution: number;
};

function fmtFeatureValue(v: number | string | null): string {
  if (v === null || v === undefined) return "n/a";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(4);
  }
  return String(v);
}

export function ShapWaterfall({ contributions }: { contributions: ShapContribution[] }) {
  const sorted = [...contributions].sort(
    (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)
  );
  const maxAbs = Math.max(...sorted.map((c) => Math.abs(c.contribution)), 0.001);

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[minmax(120px,1fr)_1fr_1fr_100px] gap-3 text-[10px] uppercase tracking-wider text-slate-500 pb-2 border-b border-slate-800">
        <div>Feature</div>
        <div className="text-right pr-4">&larr; toward legit</div>
        <div className="pl-4">toward fraud &rarr;</div>
        <div className="text-right">Contribution</div>
      </div>

      {sorted.map((c, i) => {
        const isPositive = c.contribution > 0;
        const widthPct = (Math.abs(c.contribution) / maxAbs) * 100;
        return (
          <div
            key={`${c.feature}-${i}`}
            className="grid grid-cols-[minmax(120px,1fr)_1fr_1fr_100px] gap-3 items-center text-sm"
          >
            <div>
              <div className="font-mono text-xs text-slate-200">{c.feature}</div>
              <div className="text-[10px] text-slate-500">
                value: <span className="font-mono">{fmtFeatureValue(c.value)}</span>
              </div>
            </div>
            <div className="flex justify-end">
              {!isPositive && (
                <div
                  className="h-6 bg-emerald-500/60 border-r border-emerald-400 rounded-l"
                  style={{ width: `${widthPct}%` }}
                />
              )}
            </div>
            <div>
              {isPositive && (
                <div
                  className="h-6 bg-red-500/60 border-l border-red-400 rounded-r"
                  style={{ width: `${widthPct}%` }}
                />
              )}
            </div>
            <div className={`text-right font-mono text-xs ${isPositive ? "text-red-400" : "text-emerald-400"}`}>
              {isPositive ? "+" : ""}{c.contribution.toFixed(4)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
