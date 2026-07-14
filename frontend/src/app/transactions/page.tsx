"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";
import { Tooltip, FloatingTooltip, FloatingHoverState } from "@/components/Tooltip";

type TxnSummary = {
  id: number;
  external_id: string | null;
  transaction_dt: number | null;
  amount: number;
  card1: string | null;
  product_cd: string | null;
  p_emaildomain: string | null;
  device_type: string | null;
  is_fraud: boolean | null;
  created_at: string;
  latest_score: number | null;
  latest_decision: string | null;
};

type PaginatedTxns = {
  total: number;
  page: number;
  page_size: number;
  items: TxnSummary[];
};

type Filters = {
  min_amount: string;
  max_amount: string;
  decision: string;
  min_score: string;
  max_score: string;
  is_fraud: string;
  product_cd: string;
};

const emptyFilters: Filters = {
  min_amount: "", max_amount: "", decision: "", min_score: "", max_score: "", is_fraud: "", product_cd: "",
};

const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
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

// IEEE-CIS LabelEncoder reverse maps — training encoder sorted alphabetically
// with __NA__ prepended when the column had NaN values. Used to translate the
// integer-encoded values that seed_transactions.py stored in the DB back to
// human-readable strings for display.
const IEEE_PRODUCT_CD: Record<string, string> = {
  "1": "C", "2": "H", "3": "R", "4": "S", "5": "W",
};
const IEEE_DEVICE_TYPE: Record<string, string> = {
  "1": "unknown", "2": "desktop", "3": "mobile",
};

// Display formatting for the Product / Category column. Two data sources:
//   * Sparkov-style checkout txns    → "sparkov:misc_net"  → "Sparkov · misc_net"
//   * Seeded IEEE-CIS txns           → "C", "W", …          → "IEEE · W (retail)"
//   * Also handles legacy encoded ints (1..5) via IEEE_PRODUCT_CD.
const IEEE_PRODUCT_CD_HINT: Record<string, string> = {
  "W": "web/retail",
  "C": "cash-based",
  "R": "recurring",
  "H": "household",
  "S": "special",
};

function readableProductCd(raw: string | null): { text: string; source: "sparkov" | "ieee" | "unknown" } {
  if (!raw) return { text: "—", source: "unknown" };
  // Sparkov format: "sparkov:<category>"
  if (raw.startsWith("sparkov:")) {
    const cat = raw.slice("sparkov:".length);
    return { text: cat.replace(/_/g, " "), source: "sparkov" };
  }
  // Legacy encoded int (1..5) → decode to IEEE letter
  const asNum = raw.replace(/\.0$/, "");
  if (/^\d+$/.test(asNum) && IEEE_PRODUCT_CD[asNum]) {
    const letter = IEEE_PRODUCT_CD[asNum];
    const hint = IEEE_PRODUCT_CD_HINT[letter];
    return { text: hint ? `${letter} (${hint})` : letter, source: "ieee" };
  }
  // Already a letter (W, C, R, H, S) — add hint
  if (/^[A-Z]$/.test(raw) && IEEE_PRODUCT_CD_HINT[raw]) {
    return { text: `${raw} (${IEEE_PRODUCT_CD_HINT[raw]})`, source: "ieee" };
  }
  return { text: raw, source: "unknown" };
}

function readableDeviceType(raw: string | null): string {
  if (!raw) return "—";
  const asNum = raw.replace(/\.0$/, "");
  if (/^\d+$/.test(asNum) && IEEE_DEVICE_TYPE[asNum]) return IEEE_DEVICE_TYPE[asNum];
  return raw;
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

function decisionStyle(d: string | null) {
  if (d === "block") return { bg: "rgba(239,68,68,0.12)", text: "#f87171", border: "rgba(239,68,68,0.3)" };
  if (d === "review") return { bg: "rgba(245,158,11,0.12)", text: "#fbbf24", border: "rgba(245,158,11,0.3)" };
  if (d === "approve") return { bg: "rgba(16,185,129,0.12)", text: "#34d399", border: "rgba(16,185,129,0.3)" };
  return { bg: "var(--bg-glass)", text: "var(--text-muted)", border: "var(--border-subtle)" };
}

function buildQuery(page: number, pageSize: number, f: Filters): string {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (f.min_amount) params.set("min_amount", f.min_amount);
  if (f.max_amount) params.set("max_amount", f.max_amount);
  if (f.decision) params.set("decision", f.decision);
  if (f.min_score) params.set("min_score", f.min_score);
  if (f.max_score) params.set("max_score", f.max_score);
  if (f.is_fraud) params.set("is_fraud", f.is_fraud);
  if (f.product_cd) params.set("product_cd", f.product_cd);
  return params.toString();
}

export default function TransactionsPage() {
  const router = useRouter();
  const [data, setData] = useState<PaginatedTxns | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(emptyFilters);
  const [showFilters, setShowFilters] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = buildQuery(page, pageSize, appliedFilters);
      const res = await api<PaginatedTxns>(`/api/transactions?${qs}`);
      setData(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load transactions");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, appliedFilters, router]);

  useEffect(() => { load(); }, [load]);

  const applyFilters = () => { setPage(1); setAppliedFilters(filters); };
  const clearFilters = () => { setFilters(emptyFilters); setAppliedFilters(emptyFilters); setPage(1); };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;
  const activeCount = Object.values(appliedFilters).filter(v => v !== "").length;

  return (
    <AppShell
      title="Transactions"
      subtitle={data ? `${data.total.toLocaleString()} transactions in your workspace` : "Loading…"}
      actions={
        <>
          <Tooltip content={showFilters ? "Hide filters" : "Show filters"} side="bottom">
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="px-3 h-9 rounded-lg text-sm font-medium flex items-center gap-2 transition glass glass-hover"
              style={{ color: activeCount > 0 ? "var(--accent-primary)" : "var(--text-secondary)" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
              </svg>
              <span className="hidden sm:inline">Filters</span>
              {activeCount > 0 && (
                <span className="text-[10px] font-bold px-1.5 rounded-full" style={{ background: "var(--accent-primary)", color: "white" }}>
                  {activeCount}
                </span>
              )}
            </button>
          </Tooltip>
          <Tooltip content="Refresh" side="bottom">
            <button
              onClick={load}
              className="w-9 h-9 rounded-lg flex items-center justify-center transition glass glass-hover"
              style={{ color: "var(--text-secondary)" }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
            </button>
          </Tooltip>
        </>
      }
    >
      <div>
        {showFilters && (
          <FilterBar
            filters={filters}
            setFilters={setFilters}
            onApply={applyFilters}
            onClear={clearFilters}
            activeCount={activeCount}
          />
        )}

        {error && (
          <div className="mt-4 p-4 rounded-xl" style={{ borderColor: "rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.06)", border: "1px solid" }}>
            <div className="font-semibold" style={{ color: "#f87171" }}>Failed to load transactions</div>
            <div className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{error}</div>
          </div>
        )}

        <div className={`${showFilters ? "mt-4" : ""} rounded-xl glass overflow-hidden`}>
          {loading && !data ? (
            <div className="p-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>Loading…</div>
          ) : (
            <TxnTable rows={data?.items ?? []} />
          )}
        </div>

        {data && data.total > 0 && (
          <Pagination
            page={page}
            totalPages={totalPages}
            total={data.total}
            pageSize={pageSize}
            onPage={setPage}
          />
        )}
      </div>
    </AppShell>
  );
}

function FilterBar({ filters, setFilters, onApply, onClear, activeCount }: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  onApply: () => void;
  onClear: () => void;
  activeCount: number;
}) {
  const set = (k: keyof Filters, v: string) => setFilters({ ...filters, [k]: v });
  const inputCls = "w-full h-8 rounded-lg px-3 text-xs focus:outline-none transition";
  const inputStyle = { background: "var(--bg-glass)", color: "var(--text-primary)", border: "1px solid var(--border-default)" };

  return (
    <div className="rounded-xl glass p-4 animate-fade-in">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Min $</span>
          <input type="number" value={filters.min_amount} onChange={e => set("min_amount", e.target.value)} className={inputCls} style={inputStyle} placeholder="0" />
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Max $</span>
          <input type="number" value={filters.max_amount} onChange={e => set("max_amount", e.target.value)} className={inputCls} style={inputStyle} placeholder="∞" />
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Decision</span>
          <select value={filters.decision} onChange={e => set("decision", e.target.value)} className={inputCls} style={inputStyle}>
            <option value="">Any</option>
            <option value="approve">Approve</option>
            <option value="review">Review</option>
            <option value="block">Block</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Min score</span>
          <input type="number" step="0.01" value={filters.min_score} onChange={e => set("min_score", e.target.value)} className={inputCls} style={inputStyle} placeholder="0.00" />
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Max score</span>
          <input type="number" step="0.01" value={filters.max_score} onChange={e => set("max_score", e.target.value)} className={inputCls} style={inputStyle} placeholder="1.00" />
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Label</span>
          <select value={filters.is_fraud} onChange={e => set("is_fraud", e.target.value)} className={inputCls} style={inputStyle}>
            <option value="">Any</option>
            <option value="true">Fraud</option>
            <option value="false">Legit</option>
          </select>
        </label>
        <label className="block">
          <span className="text-[10px] uppercase tracking-widest font-semibold mb-1 block" style={{ color: "var(--text-faded)" }}>Category</span>
          <input type="text" value={filters.product_cd} onChange={e => set("product_cd", e.target.value)} className={inputCls} style={inputStyle} placeholder="W, shopping_net…" />
        </label>
      </div>
      <div className="flex items-center justify-between mt-4 pt-3" style={{ borderTop: "1px solid var(--border-subtle)" }}>
        <div className="text-xs" style={{ color: "var(--text-faded)" }}>
          {activeCount > 0 ? `${activeCount} filter${activeCount === 1 ? "" : "s"} active` : "No filters applied"}
        </div>
        <div className="flex gap-2">
          <button onClick={onClear} className="px-3 h-8 rounded-lg text-xs font-medium glass glass-hover transition" style={{ color: "var(--text-muted)" }}>
            Clear
          </button>
          <button onClick={onApply} className="px-4 h-8 rounded-lg text-xs font-semibold accent-gradient text-white transition hover:scale-105">
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}

function TxnTable({ rows }: { rows: TxnSummary[] }) {
  const [hover, setHover] = useState<(FloatingHoverState & { row: TxnSummary }) | null>(null);

  if (rows.length === 0) {
    return <div className="p-8 text-center text-sm" style={{ color: "var(--text-muted)" }}>No transactions match the filters.</div>;
  }
  return (
    <>
      <table className="w-full text-sm table-fixed">
        <colgroup>
          <col style={{ width: "6%" }} />
          <col style={{ width: "14%" }} />
          <col style={{ width: "16%" }} />
          <col style={{ width: "11%" }} />
          <col style={{ width: "10%" }} />
          <col style={{ width: "12%" }} />
          <col style={{ width: "10%" }} />
          <col style={{ width: "11%" }} />
          <col style={{ width: "10%" }} />
        </colgroup>
        <thead>
          <tr style={{ background: "var(--bg-glass)", borderBottom: "1px solid var(--border-subtle)" }}>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>ID</th>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>When</th>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>External</th>
            <th className="text-right px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Amount</th>
            <th className="text-right px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Score</th>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Decision</th>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Category</th>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Device</th>
            <th className="text-left px-4 py-2.5 text-[10px] uppercase tracking-widest font-semibold" style={{ color: "var(--text-faded)" }}>Label</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const dc = decisionStyle(r.latest_decision);
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
                <td className="px-4 py-3 font-mono text-xs">
                  <Link
                    href={`/transaction?id=${r.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="hover:underline"
                    style={{ color: "var(--accent-primary)" }}
                  >
                    #{r.id}
                  </Link>
                </td>
                <td className="px-4 py-3 text-xs whitespace-nowrap" style={{ color: "var(--text-secondary)" }} title={fmtWhen(r.created_at).full}>
                  {fmtWhen(r.created_at).primary}
                </td>
                <td className="px-4 py-3 font-mono text-[11px] truncate" style={{ color: "var(--text-muted)" }}>{r.external_id ?? "—"}</td>
                <td className="px-4 py-3 text-right tabular-nums font-medium" style={{ color: "var(--text-primary)" }}>{fmtMoney(r.amount)}</td>
                <td className="px-4 py-3 text-right font-mono tabular-nums" style={{ color: "var(--text-primary)" }}>{fmtScore(r.latest_score)}</td>
                <td className="px-4 py-3">
                  <span
                    className="inline-block px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
                    style={{ background: dc.bg, border: `1px solid ${dc.border}`, color: dc.text }}
                  >
                    {r.latest_decision ?? "none"}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>
                  {(() => {
                    const p = readableProductCd(r.product_cd);
                    if (p.source === "sparkov") {
                      return (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded" style={{ background: "rgba(139,92,246,0.12)", color: "#a78bfa" }}>Sparkov</span>
                          <span style={{ color: "var(--text-primary)" }}>{p.text}</span>
                        </span>
                      );
                    }
                    if (p.source === "ieee") {
                      return (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="text-[9px] uppercase tracking-wider font-bold px-1.5 py-0.5 rounded" style={{ background: "rgba(244,63,94,0.10)", color: "#f43f5e" }}>IEEE</span>
                          <span style={{ color: "var(--text-primary)" }}>{p.text}</span>
                        </span>
                      );
                    }
                    return <span>{p.text}</span>;
                  })()}
                </td>
                <td className="px-4 py-3 text-xs truncate" style={{ color: "var(--text-muted)" }}>{readableDeviceType(r.device_type)}</td>
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

      <FloatingTooltip hover={hover}>
        {hover && (
          <div className="min-w-[240px]">
            <div className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>Transaction #{hover.row.id}</div>
            <div className="text-xs space-y-1" style={{ color: "var(--text-muted)" }}>
              <div className="flex justify-between gap-4"><span>Amount</span><span style={{ color: "var(--text-primary)" }}>{fmtMoney(hover.row.amount)}</span></div>
              <div className="flex justify-between gap-4"><span>Score</span><span style={{ color: "var(--text-primary)" }}>{fmtScore(hover.row.latest_score)}</span></div>
              <div className="flex justify-between gap-4"><span>Decision</span><span style={{ color: decisionStyle(hover.row.latest_decision).text }}>{(hover.row.latest_decision ?? "—").toUpperCase()}</span></div>
              <div className="flex justify-between gap-4"><span>Category</span><span style={{ color: "var(--text-primary)" }}>{readableProductCd(hover.row.product_cd).text}</span></div>
              <div className="flex justify-between gap-4"><span>Device</span><span style={{ color: "var(--text-primary)" }}>{readableDeviceType(hover.row.device_type)}</span></div>
              <div className="flex justify-between gap-4"><span>Email</span><span style={{ color: "var(--text-primary)" }}>{hover.row.p_emaildomain ?? "—"}</span></div>
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

function Pagination({ page, totalPages, total, pageSize, onPage }: {
  page: number; totalPages: number; total: number; pageSize: number; onPage: (p: number) => void;
}) {
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="flex items-center justify-between mt-4 text-xs" style={{ color: "var(--text-muted)" }}>
      <div>
        Showing <span style={{ color: "var(--text-primary)" }}>{from.toLocaleString()}</span>–
        <span style={{ color: "var(--text-primary)" }}>{to.toLocaleString()}</span> of{" "}
        <span style={{ color: "var(--text-primary)" }}>{total.toLocaleString()}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="px-3 h-8 rounded-lg glass glass-hover transition disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ color: "var(--text-secondary)" }}
        >
          Prev
        </button>
        <div className="px-2">
          Page <span className="font-semibold" style={{ color: "var(--text-primary)" }}>{page}</span> / {totalPages}
        </div>
        <button
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          className="px-3 h-8 rounded-lg glass glass-hover transition disabled:opacity-40 disabled:cursor-not-allowed"
          style={{ color: "var(--text-secondary)" }}
        >
          Next
        </button>
      </div>
    </div>
  );
}
