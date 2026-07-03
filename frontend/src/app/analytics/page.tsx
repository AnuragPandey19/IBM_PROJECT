"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid,
  Tooltip as RTooltip,
  Legend,
  Cell,
} from "recharts";
import { api, ApiError } from "@/lib/api";
import { getUser, logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";

type TimeBucket = {
  label: string;
  date: string;
  transactions: number;
  predictions: number;
  fraud_count: number;
  approve_count: number;
  review_count: number;
  block_count: number;
  avg_score: number;
  volume: number;
};

type TimeSeries = {
  period: string;
  buckets: TimeBucket[];
  totals: TimeBucket;
};

const fmtNum = (n: number) => new Intl.NumberFormat("en-IN").format(n);
const fmtMoney = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const fmtPct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`;

const COLORS = {
  accent: "#f43f5e",
  approve: "#10b981",
  review: "#f59e0b",
  block: "#ef4444",
  fraud: "#f87171",
  legit: "#60a5fa",
  volume: "#a78bfa",
};

// Custom tooltip for dark theme
function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ color: string; name: string; value: number }>; label?: string }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div
      className="rounded-lg p-3 text-xs shadow-2xl"
      style={{
        background: "rgba(15,15,25,0.98)",
        border: "1px solid var(--border-default)",
        backdropFilter: "blur(20px)",
      }}
    >
      <div className="font-semibold mb-1.5" style={{ color: "var(--text-primary)" }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2" style={{ color: p.color }}>
          <span className="w-2 h-2 rounded-sm" style={{ background: p.color }} />
          <span style={{ color: "var(--text-muted)" }}>{p.name}:</span>
          <span className="font-mono font-semibold">{fmtNum(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const router = useRouter();
  const [period, setPeriod] = useState<"monthly" | "yearly">("monthly");
  const [data, setData] = useState<TimeSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const user = getUser();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const limit = period === "monthly" ? 12 : 5;
      const res = await api<TimeSeries>(`/api/analytics/timeseries?period=${period}&limit=${limit}`);
      setData(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  }, [period, router]);

  useEffect(() => { load(); }, [load]);

  // Prepare chart data
  const chartData = data?.buckets.map((b) => ({
    label: b.label,
    Transactions: b.transactions,
    Predictions: b.predictions,
    Fraud: b.fraud_count,
    Approve: b.approve_count,
    Review: b.review_count,
    Block: b.block_count,
    "Avg Score": b.avg_score,
    Volume: Math.round(b.volume),
  })) ?? [];

  const totals = data?.totals;
  const fraudRate = totals && totals.transactions > 0 ? totals.fraud_count / totals.transactions : 0;

  return (
    <AppShell
      title="Analytics"
      subtitle={`${period === "monthly" ? "Last 12 months" : "Last 5 years"} of ${user?.company?.name ?? "your workspace"}`}
      actions={
        <div className="flex items-center gap-1 rounded-lg glass p-1">
          <button
            onClick={() => setPeriod("monthly")}
            className="px-3 h-7 rounded-md text-xs font-semibold transition"
            style={{
              background: period === "monthly" ? "var(--accent-bg)" : "transparent",
              color: period === "monthly" ? "var(--accent-primary)" : "var(--text-muted)",
            }}
          >
            Monthly
          </button>
          <button
            onClick={() => setPeriod("yearly")}
            className="px-3 h-7 rounded-md text-xs font-semibold transition"
            style={{
              background: period === "yearly" ? "var(--accent-bg)" : "transparent",
              color: period === "yearly" ? "var(--accent-primary)" : "var(--text-muted)",
            }}
          >
            Yearly
          </button>
        </div>
      }
    >
      {loading && !data && (
        <div className="flex items-center justify-center py-16 text-sm" style={{ color: "var(--text-muted)" }}>
          <div className="w-2 h-2 rounded-full animate-pulse-glow mr-3" style={{ background: "var(--accent-primary)" }} />
          Loading analytics…
        </div>
      )}

      {error && (
        <div className="mb-6 p-5 rounded-2xl" style={{ borderColor: "rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.06)", border: "1px solid" }}>
          <div className="font-semibold" style={{ color: "#f87171" }}>Failed to load</div>
          <div className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{error}</div>
        </div>
      )}

      {data && totals && (
        <div className="space-y-6 stagger">
          {/* Period KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatCard label="Transactions" value={fmtNum(totals.transactions)} sub={`${fmtNum(totals.predictions)} scored`} />
            <StatCard label="Fraud rate" value={fmtPct(fraudRate)} sub={`${fmtNum(totals.fraud_count)} confirmed`} accent />
            <StatCard label="Avg risk" value={totals.avg_score.toFixed(3)} sub="Calibrated" />
            <StatCard label="Volume" value={fmtMoney(totals.volume)} sub={period === "monthly" ? "12 months" : "5 years"} />
          </div>

          {/* Transaction volume trend */}
          <ChartSection title="Transaction volume trend" subtitle={`Total transactions per ${period === "monthly" ? "month" : "year"}`}>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="fillTxns" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.accent} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={COLORS.accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="label" tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                <YAxis tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                <RTooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="Transactions" stroke={COLORS.accent} strokeWidth={2} fill="url(#fillTxns)" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartSection>

          {/* Decision breakdown stacked bar */}
          <ChartSection title="Decision breakdown" subtitle="Approve / Review / Block routing per period">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="label" tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                <YAxis tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                <RTooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ paddingTop: 12, fontSize: 12, color: "var(--text-muted)" }} />
                <Bar dataKey="Approve" stackId="d" fill={COLORS.approve} radius={[0, 0, 0, 0]} />
                <Bar dataKey="Review" stackId="d" fill={COLORS.review} radius={[0, 0, 0, 0]} />
                <Bar dataKey="Block" stackId="d" fill={COLORS.block} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartSection>

          {/* Fraud vs Legit + Avg score side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartSection title="Confirmed fraud volume" subtitle="Rows labelled as fraud in ground truth">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="label" tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                  <YAxis tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                  <RTooltip content={<ChartTooltip />} />
                  <Bar dataKey="Fraud" radius={[6, 6, 0, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={COLORS.fraud} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartSection>

            <ChartSection title="Average risk score" subtitle="Calibrated probability trend">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                  <XAxis dataKey="label" tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                  <YAxis domain={[0, "dataMax + 0.1"]} tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                  <RTooltip content={<ChartTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="Avg Score"
                    stroke={COLORS.accent}
                    strokeWidth={2.5}
                    dot={{ fill: COLORS.accent, r: 4 }}
                    activeDot={{ r: 6, stroke: "var(--bg-base)", strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartSection>
          </div>

          {/* Volume USD */}
          <ChartSection title="Transaction volume (USD)" subtitle="Total monetary value processed per period">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="fillVol" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.volume} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={COLORS.volume} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="label" tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" />
                <YAxis tick={{ fill: "var(--text-faded)", fontSize: 11 }} stroke="var(--border-default)" tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
                <RTooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="Volume" stroke={COLORS.volume} strokeWidth={2} fill="url(#fillVol)" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartSection>
        </div>
      )}
    </AppShell>
  );
}

function StatCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div
      className="rounded-xl p-4 transition glass glass-hover"
      style={accent ? { borderColor: "rgba(244,63,94,0.2)", background: "linear-gradient(135deg, rgba(244,63,94,0.05) 0%, var(--bg-glass) 100%)" } : undefined}
    >
      <div className="text-[10px] uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--text-faded)" }}>{label}</div>
      <div className="text-2xl font-bold tabular-nums leading-tight" style={{ color: accent ? "var(--accent-primary)" : "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
        {value}
      </div>
      {sub && <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</div>}
    </div>
  );
}

function ChartSection({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl glass p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
        {subtitle && <div className="text-xs mt-0.5" style={{ color: "var(--text-faded)" }}>{subtitle}</div>}
      </div>
      {children}
    </section>
  );
}
