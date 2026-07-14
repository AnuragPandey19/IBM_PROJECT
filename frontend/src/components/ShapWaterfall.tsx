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
    // role=table so assistive tech announces the columns semantically.
    <div role="table" aria-label="SHAP feature contributions" className="space-y-2">
      <div
        role="row"
        className="grid grid-cols-[minmax(120px,1fr)_1fr_1fr_100px] gap-3 text-[10px] uppercase tracking-wider text-slate-500 pb-2 border-b border-slate-800"
      >
        <div role="columnheader">Feature</div>
        <div role="columnheader" className="text-right pr-4">← toward legit</div>
        <div role="columnheader" className="pl-4">toward fraud →</div>
        <div role="columnheader" className="text-right">Contribution</div>
      </div>

      {sorted.map((c, i) => {
        const isPositive = c.contribution > 0;
        const widthPct = (Math.abs(c.contribution) / maxAbs) * 100;
        const direction = isPositive ? "toward fraud" : "toward legit";
        const contribText = `${isPositive ? "+" : ""}${c.contribution.toFixed(4)}`;
        // Human-readable label for screen readers: covers direction, magnitude,
        // and the underlying feature value.
        const ariaLabel =
          `Feature ${c.feature} contributes ${contribText} ${direction}. ` +
          `Feature value: ${fmtFeatureValue(c.value)}.`;
        return (
          <div
            role="row"
            aria-label={ariaLabel}
            key={`${c.feature}-${i}`}
            className="grid grid-cols-[minmax(120px,1fr)_1fr_1fr_100px] gap-3 items-center text-sm focus-within:ring-1 focus-within:ring-slate-500 rounded"
            tabIndex={0}
          >
            <div role="cell">
              <div className="font-mono text-xs text-slate-200">{c.feature}</div>
              <div className="text-[10px] text-slate-500">
                value: <span className="font-mono">{fmtFeatureValue(c.value)}</span>
              </div>
            </div>
            <div role="cell" aria-hidden="true" className="flex justify-end">
              {!isPositive && (
                <div
                  className="h-6 bg-emerald-500/60 border-r border-emerald-400 rounded-l"
                  style={{ width: `${widthPct}%` }}
                />
              )}
            </div>
            <div role="cell" aria-hidden="true">
              {isPositive && (
                <div
                  className="h-6 bg-red-500/60 border-l border-red-400 rounded-r"
                  style={{ width: `${widthPct}%` }}
                />
              )}
            </div>
            <div
              role="cell"
              className={`text-right font-mono text-xs ${isPositive ? "text-red-400" : "text-emerald-400"}`}
            >
              {/* Include an explicit +/- prefix and a color-independent symbol so
                  colorblind users can still tell fraud vs legit at a glance. */}
              <span className="sr-only">{direction}: </span>
              {contribText}
              <span aria-hidden="true" className="ml-1 text-[9px] opacity-70">
                {isPositive ? "↑" : "↓"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
