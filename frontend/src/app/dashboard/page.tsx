"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";

// -------- Types matching backend /api/metrics/summary --------
type DecisionCounts = { approve: number; review: number; block: number };
type AmountStats = { total: number; avg: number; max: number };
type RiskyTxn = {
  id: number;
  external_id: string | null;
  amount: number;
  calibrated_score: number | null;
  raw_score: number;
  decision: string;
  product_cd: string | null;
  is_fraud: boolean | null;
  created_at: string;
};
type MetricsSummary = {
  total_transactions: number;
  total_predictions: number;
  fraud_count: number;
  fraud_rate: number;
  decision_counts: DecisionCounts;
  avg_calibrated_score: number | null;
  amount_stats: AmountStats;
  top_risky: RiskyTxn[];
  model_version: string | null;
};

// -------- Helpers --------
const fmtNum = (n: number) => new Intl.NumberFormat("en-IN").format(n);
const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const fmtPct = (n: number, digits = 2) => `${(n * 100).toFixed(digits)}%`;
const fmtScore = (n: number | null) => (n === null ? "-" : n.toFixed(4));

function decisionColor(d: string): string {
  if (d === "block") return "text-red-400 bg-red-500/10 border-red-500/30";
  if (d === "review") return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
}

// -------- Page --------
export default function DashboardPage() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMetrics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadMetrics() {
    setLoading(true);
    setError(null);
    try {
      const data = await api<MetricsSummary>("/api/metrics/summary");
      setMetrics(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell
      title="Analyst Dashboard"
      subtitle="Live KPIs from production database"
      actions={
        <button
          onClick={loadMetrics}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700"
        >
          Refresh
        </button>
      }
    >
      {loading && (
        <div className="text-slate-400 text-sm">Loading metrics&hellip;</div>
      )}

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300">
          <div className="font-semibold">Failed to load metrics</div>
          <div className="text-sm mt-1">{error}</div>
          <button
            onClick={loadMetrics}
            className="mt-3 px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-sm border border-red-500/40"
          >
            Retry
          </button>
        </div>
      )}

      {metrics && !error && (
        <>
          {/* KPI cards row */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <KpiCard
              label="Total Transactions"
              value={fmtNum(metrics.total_transactions)}
              sub={`${fmtNum(metrics.total_predictions)} predictions`}
              accent="slate"
            />
            <KpiCard
              label="Fraud Rate (labelled)"
              value={fmtPct(metrics.fraud_rate)}
              sub={`${fmtNum(metrics.fraud_count)} confirmed fraud`}
              accent="red"
            />
            <KpiCard
              label="Avg Calibrated Risk"
              value={fmtScore(metrics.avg_calibrated_score)}
              sub={metrics.model_version || "no predictions yet"}
              accent="amber"
            />
            <KpiCard
              label="Total Amount"
              value={fmtMoney(metrics.amount_stats.total)}
              sub={`avg ${fmtMoney(metrics.amount_stats.avg)} / max ${fmtMoney(metrics.amount_stats.max)}`}
              accent="emerald"
            />
          </div>

          {/* Decision breakdown */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold mb-3">Decision Breakdown</h2>
            <DecisionBar counts={metrics.decision_counts} />
          </div>

          {/* Top risky transactions */}
          <div>
            <h2 className="text-lg font-semibold mb-3">
              Top 10 High-Risk Transactions
            </h2>
            <RiskyTable rows={metrics.top_risky} />
          </div>
        </>
      )}
    </AppShell>
  );
}

// -------- Sub-components --------

function KpiCard({
  label, value, sub, accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: "slate" | "red" | "amber" | "emerald";
}) {
  const border = {
    slate: "border-slate-700",
    red: "border-red-500/40",
    amber: "border-amber-500/40",
    emerald: "border-emerald-500/40",
  }[accent];
  const dot = {
    slate: "bg-slate-500",
    red: "bg-red-500",
    amber: "bg-amber-500",
    emerald: "bg-emerald-500",
  }[accent];

  return (
    <div className={`bg-slate-900/60 border ${border} rounded-2xl p-5`}>
      <div className="flex items-center gap-2 text-xs text-slate-400 uppercase tracking-wider">
        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
        {label}
      </div>
      <div className="text-3xl font-bold mt-2">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}

function DecisionBar({ counts }: { counts: DecisionCounts }) {
  const total = counts.approve + counts.review + counts.block;
  if (total === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 text-slate-500 text-sm">
        No predictions yet.
      </div>
    );
  }
  const pct = (n: number) => (n / total) * 100;
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5">
      <div className="flex h-3 rounded-full overflow-hidden bg-slate-800">
        <div className="bg-emerald-500" style={{ width: `${pct(counts.approve)}%` }} />
        <div className="bg-amber-500" style={{ width: `${pct(counts.review)}%` }} />
        <div className="bg-red-500" style={{ width: `${pct(counts.block)}%` }} />
      </div>
      <div className="grid grid-cols-3 gap-4 mt-4 text-sm">
        <LegendItem color="bg-emerald-500" label="Approve" count={counts.approve} total={total} />
        <LegendItem color="bg-amber-500" label="Review" count={counts.review} total={total} />
        <LegendItem color="bg-red-500" label="Block" count={counts.block} total={total} />
      </div>
    </div>
  );
}

function LegendItem({
  color, label, count, total,
}: { color: string; label: string; count: number; total: number }) {
  const pct = total === 0 ? 0 : (count / total) * 100;
  return (
    <div>
      <div className="flex items-center gap-2 text-slate-300">
        <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
        <span className="font-medium">{label}</span>
      </div>
      <div className="text-xl font-bold mt-1">{fmtNum(count)}</div>
      <div className="text-xs text-slate-500">{pct.toFixed(1)}% of predictions</div>
    </div>
  );
}

function RiskyTable({ rows }: { rows: RiskyTxn[] }) {
  if (rows.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 text-slate-500 text-sm">
        No predictions in the database yet. Run the seed script or use /api/predict.
      </div>
    );
  }
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-900/80 text-slate-400 uppercase text-[11px] tracking-wider">
          <tr>
            <th className="text-left px-4 py-3">ID</th>
            <th className="text-left px-4 py-3">External</th>
            <th className="text-right px-4 py-3">Amount</th>
            <th className="text-right px-4 py-3">Calibrated</th>
            <th className="text-right px-4 py-3">Raw</th>
            <th className="text-left px-4 py-3">Decision</th>
            <th className="text-left px-4 py-3">Product</th>
            <th className="text-left px-4 py-3">Label</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-slate-800/40 transition">
              <td className="px-4 py-3 font-mono text-slate-300">#{r.id}</td>
              <td className="px-4 py-3 font-mono text-xs text-slate-400">{r.external_id ?? "-"}</td>
              <td className="px-4 py-3 text-right">{fmtMoney(r.amount)}</td>
              <td className="px-4 py-3 text-right font-mono">{fmtScore(r.calibrated_score)}</td>
              <td className="px-4 py-3 text-right font-mono text-slate-400">{r.raw_score.toFixed(4)}</td>
              <td className="px-4 py-3">
                <span className={`inline-block px-2 py-0.5 rounded-md border text-xs font-semibold uppercase tracking-wider ${decisionColor(r.decision)}`}>
                  {r.decision}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-400">{r.product_cd ?? "-"}</td>
              <td className="px-4 py-3">
                {r.is_fraud === true && <span className="text-red-400 text-xs font-semibold">FRAUD</span>}
                {r.is_fraud === false && <span className="text-slate-500 text-xs">legit</span>}
                {r.is_fraud === null && <span className="text-slate-600 text-xs">-</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
