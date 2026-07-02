"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";

// -------- Types matching backend /api/transactions --------
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

// -------- Filter state --------
type Filters = {
  min_amount: string;
  max_amount: string;
  decision: string;
  min_score: string;
  max_score: string;
  is_fraud: string; // "", "true", "false"
  product_cd: string;
};

const emptyFilters: Filters = {
  min_amount: "",
  max_amount: "",
  decision: "",
  min_score: "",
  max_score: "",
  is_fraud: "",
  product_cd: "",
};

// -------- Helpers --------
const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const fmtScore = (n: number | null) => (n === null ? "-" : n.toFixed(4));

function decisionColor(d: string | null): string {
  if (d === "block") return "text-red-400 bg-red-500/10 border-red-500/30";
  if (d === "review") return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  if (d === "approve") return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  return "text-slate-500 bg-slate-800 border-slate-700";
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

// -------- Page --------
export default function TransactionsPage() {
  const router = useRouter();
  const [data, setData] = useState<PaginatedTxns | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(emptyFilters);

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

  useEffect(() => {
    load();
  }, [load]);

  function applyFilters() {
    setPage(1);
    setAppliedFilters(filters);
  }

  function clearFilters() {
    setFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
    setPage(1);
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;
  const activeFilterCount = Object.values(appliedFilters).filter(v => v !== "").length;

  return (
    <AppShell
      title="Transactions"
      subtitle={data ? `${data.total.toLocaleString()} total, showing ${data.items.length} on page ${page}` : "Loading…"}
      actions={
        <button
          onClick={load}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700"
        >
          Refresh
        </button>
      }
    >
      {/* Filter bar */}
      <FilterBar
        filters={filters}
        setFilters={setFilters}
        onApply={applyFilters}
        onClear={clearFilters}
        activeCount={activeFilterCount}
      />

      {/* Error */}
      {error && (
        <div className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300">
          <div className="font-semibold">Failed to load transactions</div>
          <div className="text-sm mt-1">{error}</div>
        </div>
      )}

      {/* Table */}
      <div className="mt-4 bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
        {loading && !data ? (
          <div className="p-8 text-center text-slate-500 text-sm">Loading&hellip;</div>
        ) : (
          <TxnTable rows={data?.items ?? []} />
        )}
      </div>

      {/* Pagination */}
      {data && data.total > 0 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          total={data.total}
          pageSize={pageSize}
          onPage={setPage}
        />
      )}
    </AppShell>
  );
}

// -------- Sub-components --------

function FilterBar({
  filters, setFilters, onApply, onClear, activeCount,
}: {
  filters: Filters;
  setFilters: (f: Filters) => void;
  onApply: () => void;
  onClear: () => void;
  activeCount: number;
}) {
  const set = (k: keyof Filters, v: string) => setFilters({ ...filters, [k]: v });

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <NumberInput label="Min Amount" value={filters.min_amount} onChange={(v) => set("min_amount", v)} placeholder="$0" />
        <NumberInput label="Max Amount" value={filters.max_amount} onChange={(v) => set("max_amount", v)} placeholder="$" />
        <SelectInput
          label="Decision"
          value={filters.decision}
          onChange={(v) => set("decision", v)}
          options={[
            { value: "", label: "Any" },
            { value: "approve", label: "Approve" },
            { value: "review", label: "Review" },
            { value: "block", label: "Block" },
          ]}
        />
        <NumberInput label="Min Score" value={filters.min_score} onChange={(v) => set("min_score", v)} placeholder="0.00" step="0.01" />
        <NumberInput label="Max Score" value={filters.max_score} onChange={(v) => set("max_score", v)} placeholder="1.00" step="0.01" />
        <SelectInput
          label="Label"
          value={filters.is_fraud}
          onChange={(v) => set("is_fraud", v)}
          options={[
            { value: "", label: "Any" },
            { value: "true", label: "Fraud" },
            { value: "false", label: "Legit" },
          ]}
        />
        <TextInput label="Product" value={filters.product_cd} onChange={(v) => set("product_cd", v)} placeholder="W / H / C…" />
      </div>
      <div className="flex items-center justify-between mt-4">
        <div className="text-xs text-slate-500">
          {activeCount > 0 ? `${activeCount} filter${activeCount === 1 ? "" : "s"} active` : "No filters applied"}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onClear}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm border border-slate-700"
          >
            Clear
          </button>
          <button
            onClick={onApply}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-sm"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}

function NumberInput({
  label, value, onChange, placeholder, step,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  step?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wider text-slate-400">{label}</span>
      <input
        type="number"
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-red-500"
      />
    </label>
  );
}

function TextInput({
  label, value, onChange, placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wider text-slate-400">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-red-500"
      />
    </label>
  );
}

function SelectInput({
  label, value, onChange, options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wider text-slate-400">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-red-500"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

function TxnTable({ rows }: { rows: TxnSummary[] }) {
  if (rows.length === 0) {
    return <div className="p-8 text-center text-slate-500 text-sm">No transactions match the filters.</div>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-slate-900/80 text-slate-400 uppercase text-[11px] tracking-wider">
        <tr>
          <th className="text-left px-4 py-3">ID</th>
          <th className="text-left px-4 py-3">External</th>
          <th className="text-right px-4 py-3">Amount</th>
          <th className="text-right px-4 py-3">Score</th>
          <th className="text-left px-4 py-3">Decision</th>
          <th className="text-left px-4 py-3">Product</th>
          <th className="text-left px-4 py-3">Device</th>
          <th className="text-left px-4 py-3">Label</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-800">
        {rows.map((r) => (
          <tr
            key={r.id}
            className="hover:bg-slate-800/40 cursor-pointer transition group"
            onClick={() => { window.location.href = `/transaction?id=${r.id}`; }}
          >
            <td className="px-4 py-3 font-mono text-slate-300">
              <Link href={`/transaction?id=${r.id}`} className="text-red-400 group-hover:underline" onClick={(e) => e.stopPropagation()}>
                #{r.id}
              </Link>
            </td>
            <td className="px-4 py-3 font-mono text-xs text-slate-400">{r.external_id ?? "-"}</td>
            <td className="px-4 py-3 text-right">{fmtMoney(r.amount)}</td>
            <td className="px-4 py-3 text-right font-mono">{fmtScore(r.latest_score)}</td>
            <td className="px-4 py-3">
              <span className={`inline-block px-2 py-0.5 rounded-md border text-xs font-semibold uppercase tracking-wider ${decisionColor(r.latest_decision)}`}>
                {r.latest_decision ?? "none"}
              </span>
            </td>
            <td className="px-4 py-3 text-slate-400">{r.product_cd ?? "-"}</td>
            <td className="px-4 py-3 text-slate-400">{r.device_type ?? "-"}</td>
            <td className="px-4 py-3">
              {r.is_fraud === true && <span className="text-red-400 text-xs font-semibold">FRAUD</span>}
              {r.is_fraud === false && <span className="text-slate-500 text-xs">legit</span>}
              {r.is_fraud === null && <span className="text-slate-600 text-xs">-</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Pagination({
  page, totalPages, total, pageSize, onPage,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPage: (p: number) => void;
}) {
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="flex items-center justify-between mt-4">
      <div className="text-sm text-slate-500">
        Showing <span className="text-slate-300">{from.toLocaleString()}</span>&ndash;
        <span className="text-slate-300">{to.toLocaleString()}</span> of{" "}
        <span className="text-slate-300">{total.toLocaleString()}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm border border-slate-700"
        >
          Prev
        </button>
        <div className="text-sm text-slate-400 px-3">
          Page <span className="text-slate-100 font-semibold">{page}</span> / {totalPages}
        </div>
        <button
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm border border-slate-700"
        >
          Next
        </button>
      </div>
    </div>
  );
}
