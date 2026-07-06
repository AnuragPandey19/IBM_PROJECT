"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { getUser, logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";
import { Tooltip, FloatingTooltip, FloatingHoverState } from "@/components/Tooltip";

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

const fmtNum = (n: number) => new Intl.NumberFormat("en-IN").format(n);
const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const fmtPct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`;
const fmtScore = (n: number | null) => (n === null ? "—" : n.toFixed(3));

// Local-timezone datetime — browser auto-detects user's timezone from ISO UTC string.
// Backend sometimes emits ISO without a trailing 'Z' (SQLite tz-naive DateTime), which
// JS would then treat as LOCAL time. Force UTC parsing by appending 'Z' if missing.
function parseServerIso(iso: string): Date {
  const s = iso.trim();
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/i.test(s);
  return new Date(hasTz ? s : s + "Z");
}

function fmtWhen(iso: string | null | undefined): { primary: string; full: string } {
  if (!iso) return { primary: "—", full: "" };
  try {
    const d = parseServerIso(iso);
    if (isNaN(d.getTime())) return { primary: "—", full: "" };
    const now = new Date();
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const isYesterday =
      d.getFullYear() === yesterday.getFullYear() &&
      d.getMonth() === yesterday.getMonth() &&
      d.getDate() === yesterday.getDate();
    const timeStr = d.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
    let primary: string;
    if (sameDay) primary = `Today, ${timeStr}`;
    else if (isYesterday) primary = `Yesterday, ${timeStr}`;
    else
      primary = d.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
      }) + `, ${timeStr}`;
    // Full = for tooltip / accessibility
    const full = d.toLocaleString(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
      timeZoneName: "short",
    });
    return { primary, full };
  } catch {
    return { primary: "—", full: "" };
  }
}

// IEEE-CIS LabelEncoder reverse map for the seeded transactions' product_cd,
// which was stored as an int (e.g. "5") instead of the original string ("W").
const IEEE_PRODUCT_CD: Record<string, string> = {
  "1": "C", "2": "H", "3": "R", "4": "S", "5": "W",
};
const IEEE_PRODUCT_CD_HINT: Record<string, string> = {
  "W": "web/retail",
  "C": "cash-based",
  "R": "recurring",
  "H": "household",
  "S": "special",
};

function readableProductCd(raw: string | null): { text: string; source: "sparkov" | "ieee" | "unknown" } {
  if (!raw) return { text: "—", source: "unknown" };
  if (raw.startsWith("sparkov:")) {
    const cat = raw.slice("sparkov:".length);
    return { text: cat.replace(/_/g, " "), source: "sparkov" };
  }
  const asNum = raw.replace(/\.0$/, "");
  if (/^\d+$/.test(asNum) && IEEE_PRODUCT_CD[asNum]) {
    const letter = IEEE_PRODUCT_CD[asNum];
    const hint = IEEE_PRODUCT_CD_HINT[letter];
    return { text: hint ? `${letter} (${hint})` : letter, source: "ieee" };
  }
  if (/^[A-Z]$/.test(raw) && IEEE_PRODUCT_CD_HINT[raw]) {
    return { text: `${raw} (${IEEE_PRODUCT_CD_HINT[raw]})`, source: "ieee" };
  }
  return { text: raw, source: "unknown" };
}

function labelBadge(isFraud: boolean | null) {
  if (isFraud === true) {
    return { text: "FRAUD", color: "#f87171", bg: "rgba(239,68,68,0.10)", border: "rgba(239,68,68,0.30)" };
  }
  if (isFraud === false) {
    return { text: "LEGIT", color: "#34d399", bg: "rgba(16,185,129,0.10)", border: "rgba(16,185,129,0.28)" };
  }
  return { text: "PENDING", color: "var(--text-faded)", bg: "var(--bg-glass)", border: "var(--border-subtle)" };
}

function decisionStyle(d: string) {
  if (d === "block") return { bg: "rgba(239,68,68,0.12)", text: "#f87171", border: "rgba(239,68,68,0.3)" };
  if (d === "review") return { bg: "rgba(245,158,11,0.12)", text: "#fbbf24", border: "rgba(245,158,11,0.3)" };
  return { bg: "rgba(16,185,129,0.12)", text: "#34d399", border: "rgba(16,185,129,0.3)" };
}

export default function DashboardPage() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const user = getUser();

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
      subtitle={user?.company?.name ? `Fraud operations overview for ${user.company.name}` : undefined}
      actions={
        <Tooltip content="Refresh metrics" side="bottom">
          <button
            onClick={loadMetrics}
            className="px-3 h-9 rounded-lg text-sm font-medium flex items-center gap-2 transition glass glass-hover"
            style={{ color: "var(--text-secondary)" }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </Tooltip>
      }
    >
      {loading && !metrics && (
        <div className="flex items-center justify-center py-16 text-sm" style={{ color: "var(--text-muted)" }}>
          <div className="w-2 h-2 rounded-full animate-pulse-glow mr-3" style={{ background: "var(--accent-primary)" }} />
          Loading metrics&hellip;
        </div>
      )}

      {error && (
        <div className="mb-6 p-5 rounded-2xl" style={{ borderColor: "rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.06)", border: "1px solid" }}>
          <div className="font-semibold" style={{ color: "#f87171" }}>Failed to load metrics</div>
          <div className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{error}</div>
          <button
            onClick={loadMetrics}
            className="mt-3 px-4 py-2 rounded-lg text-sm border transition"
            style={{ borderColor: "rgba(239,68,68,0.4)", color: "#f87171", background: "rgba(239,68,68,0.1)" }}
          >
            Retry
          </button>
        </div>
      )}

      {metrics && !error && (
        <div className="space-y-6 stagger">
          {/* KPI grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <KpiCard label="Transactions" value={fmtNum(metrics.total_transactions)} delta={`${fmtNum(metrics.total_predictions)} scored`} />
            <KpiCard label="Fraud rate" value={fmtPct(metrics.fraud_rate)} delta={`${fmtNum(metrics.fraud_count)} confirmed`} accent />
            <KpiCard label="Avg risk" value={fmtScore(metrics.avg_calibrated_score)} delta="Calibrated" />
            <KpiCard label="Volume" value={fmtMoney(metrics.amount_stats.total)} delta={`Avg ${fmtMoney(metrics.amount_stats.avg)}`} />
          </div>

          {/* Decision breakdown */}
          <section>
            <SectionHeader title="Decision breakdown" subtitle="Model routing across the review queue" />
            <DecisionBar counts={metrics.decision_counts} />
          </section>

          {/* Top risky */}
          <section>
            <SectionHeader
              title="Top high-risk transactions"
              subtitle="Sorted by calibrated risk score"
              action={
                <Link href="/transactions" className="text-xs font-medium flex items-center gap-1 transition hover:gap-2" style={{ color: "var(--accent-primary)" }}>
                  View all
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </Link>
              }
            />
            <RiskyTable rows={metrics.top_risky} />
          </section>
        </div>
      )}
    </AppShell>
  );
}

function SectionHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-3 gap-3 flex-wrap">
      <div>
        <h2 className="text-sm font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>{title}</h2>
        {subtitle && <div className="text-xs mt-0.5" style={{ color: "var(--text-faded)" }}>{subtitle}</div>}
      </div>
      {action}
    </div>
  );
}

function KpiCard({ label, value, delta, accent }: { label: string; value: string; delta?: string; accent?: boolean }) {
  return (
    <div
      className="rounded-xl p-4 transition glass glass-hover"
      style={
        accent
          ? { borderColor: "rgba(244,63,94,0.2)", background: "linear-gradient(135deg, rgba(244,63,94,0.05) 0%, var(--bg-glass) 100%)" }
          : undefined
      }
    >
      <div className="text-[10px] uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--text-faded)" }}>
        {label}
      </div>
      <div className="text-2xl font-bold tabular-nums leading-tight" style={{ color: accent ? "var(--accent-primary)" : "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
        {value}
      </div>
      {delta && <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{delta}</div>}
    </div>
  );
}

function DecisionBar({ counts }: { counts: DecisionCounts }) {
  const total = counts.approve + counts.review + counts.block;
  if (total === 0) {
    return (
      <div className="rounded-xl p-8 text-center glass text-sm" style={{ color: "var(--text-muted)" }}>
        No predictions yet.{" "}
        <Link href="/predict" style={{ color: "var(--accent-primary)" }} className="hover:underline">Score your first transaction</Link>.
      </div>
    );
  }
  const pct = (n: number) => (n / total) * 100;

  return (
    <div className="rounded-xl glass p-5">
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-[11px] uppercase tracking-widest" style={{ color: "var(--text-faded)" }}>Distribution</span>
        <span className="text-sm font-mono tabular-nums" style={{ color: "var(--text-muted)" }}>{fmtNum(total)} total</span>
      </div>
      <div className="flex h-2 rounded-full overflow-hidden mb-4" style={{ background: "var(--border-subtle)" }}>
        <div style={{ width: `${pct(counts.approve)}%`, background: "linear-gradient(90deg, #10b981, #34d399)" }} />
        <div style={{ width: `${pct(counts.review)}%`, background: "linear-gradient(90deg, #f59e0b, #fbbf24)" }} />
        <div style={{ width: `${pct(counts.block)}%`, background: "linear-gradient(90deg, #ef4444, #f87171)" }} />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Legend color="#10b981" label="Approve" count={counts.approve} pct={pct(counts.approve)} />
        <Legend color="#f59e0b" label="Review" count={counts.review} pct={pct(counts.review)} />
        <Legend color="#ef4444" label="Block" count={counts.block} pct={pct(counts.block)} />
      </div>
    </div>
  );
}

function Legend({ color, label, count, pct }: { color: string; label: string; count: number; pct: number }) {
  return (
    <div className="p-2.5 rounded-lg glass glass-hover transition w-full">
      <div className="flex items-center gap-1.5 mb-1">
        <span className="w-2 h-2 rounded-sm" style={{ background: color }} />
        <span className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>{label}</span>
      </div>
      <div className="text-lg font-bold tabular-nums" style={{ color: "var(--text-primary)" }}>{fmtNum(count)}</div>
      <div className="text-[10px]" style={{ color: "var(--text-faded)" }}>{pct.toFixed(1)}% of queue</div>
    </div>
  );
}

/**
 * Risky transactions table with a portal-based floating tooltip.
 * The tooltip content is rendered to document.body via FloatingTooltip,
 * so no <tr> ends up nested inside a <div> — no hydration error.
 */
function RiskyTable({ rows }: { rows: RiskyTxn[] }) {
  const [hover, setHover] = useState<(FloatingHoverState & { row: RiskyTxn }) | null>(null);

  if (rows.length === 0) {
    return (
      <div className="rounded-xl glass p-10 text-center">
        <div className="text-sm mb-1" style={{ color: "var(--text-secondary)" }}>No predictions yet</div>
        <div className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>Score your first transaction to see it here.</div>
        <Link href="/predict" className="inline-block px-4 py-2 rounded-lg text-sm font-semibold accent-gradient text-white transition hover:scale-[1.02]">
          Go to Live Predict
        </Link>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-xl glass overflow-hidden">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            <col style={{ width: "7%" }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "18%" }} />
            <col style={{ width: "12%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "15%" }} />
            <col style={{ width: "12%" }} />
          </colgroup>
          <thead>
            <tr style={{ background: "var(--bg-glass)", borderBottom: "1px solid var(--border-subtle)" }}>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>ID</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>When</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>External</th>
              <th className="text-right px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Amount</th>
              <th className="text-right px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Cal.</th>
              <th className="text-right px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Raw</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Decision</th>
              <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Label</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const dc = decisionStyle(r.decision);
              return (
                <tr
                  key={r.id}
                  className="cursor-pointer transition"
                  style={{ borderTop: "1px solid var(--border-subtle)" }}
                  onMouseEnter={(e) => setHover({ x: e.clientX, y: e.clientY, row: r })}
                  onMouseMove={(e) => setHover((h) => (h ? { ...h, x: e.clientX, y: e.clientY } : null))}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => (window.location.href = `/transaction?id=${r.id}`)}
                  onMouseOver={(e) => (e.currentTarget.style.background = "var(--bg-glass)")}
                  onMouseOut={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--accent-primary)" }}>#{r.id}</td>
                  <td className="px-4 py-3 text-xs whitespace-nowrap" style={{ color: "var(--text-secondary)" }} title={fmtWhen(r.created_at).full}>
                    {fmtWhen(r.created_at).primary}
                  </td>
                  <td className="px-4 py-3 font-mono text-[11px] truncate" style={{ color: "var(--text-muted)" }}>{r.external_id ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{fmtMoney(r.amount)}</td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums" style={{ color: "var(--text-primary)" }}>{fmtScore(r.calibrated_score)}</td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-xs" style={{ color: "var(--text-muted)" }}>{r.raw_score.toFixed(3)}</td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-block px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
                      style={{ background: dc.bg, border: `1px solid ${dc.border}`, color: dc.text }}
                    >
                      {r.decision}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs">
                    {(() => {
                      const b = labelBadge(r.is_fraud);
                      return (
                        <span
                          className="inline-block px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
                          style={{ background: b.bg, border: `1px solid ${b.border}`, color: b.color }}
                        >
                          {b.text}
                        </span>
                      );
                    })()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <FloatingTooltip hover={hover}>
        {hover && (
          <div className="min-w-[220px]">
            <div className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              Transaction #{hover.row.id}
            </div>
            <div className="text-xs space-y-1" style={{ color: "var(--text-muted)" }}>
              <div className="flex justify-between gap-4"><span>When</span><span style={{ color: "var(--text-primary)" }}>{fmtWhen(hover.row.created_at).primary}</span></div>
              <div className="flex justify-between gap-4"><span>Amount</span><span style={{ color: "var(--text-primary)" }}>{fmtMoney(hover.row.amount)}</span></div>
              <div className="flex justify-between gap-4"><span>Calibrated</span><span style={{ color: "var(--text-primary)" }}>{fmtScore(hover.row.calibrated_score)}</span></div>
              <div className="flex justify-between gap-4"><span>Raw score</span><span style={{ color: "var(--text-primary)" }}>{hover.row.raw_score.toFixed(4)}</span></div>
              <div className="flex justify-between gap-4"><span>Decision</span><span style={{ color: decisionStyle(hover.row.decision).text }}>{hover.row.decision.toUpperCase()}</span></div>
              <div className="flex justify-between gap-4"><span>Category</span><span style={{ color: "var(--text-primary)" }}>{readableProductCd(hover.row.product_cd).text}</span></div>
              <div className="flex justify-between gap-4 items-center">
                <span>Label</span>
                {(() => {
                  const b = labelBadge(hover.row.is_fraud);
                  return (
                    <span
                      className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider"
                      style={{ background: b.bg, border: `1px solid ${b.border}`, color: b.color }}
                    >
                      {b.text}
                    </span>
                  );
                })()}
              </div>
            </div>
            <div className="mt-2 pt-2 border-t text-[10px]" style={{ borderColor: "var(--border-subtle)", color: "var(--text-faded)" }}>
              Click for full detail + SHAP →
            </div>
          </div>
        )}
      </FloatingTooltip>
    </>
  );
}
