"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";
import { ShapWaterfall, ShapContribution } from "@/components/ShapWaterfall";

type PredictionSummary = {
  id: number;
  raw_score: number;
  calibrated_score: number | null;
  decision: string;
  model_version: string;
  latency_ms: number | null;
  shap_top: ShapContribution[] | null;
  created_at: string;
};

type TxnDetail = {
  id: number;
  external_id: string | null;
  transaction_dt: number | null;
  amount: number;
  card1: string | null;
  card4: string | null;
  card6: string | null;
  product_cd: string | null;
  addr1: string | null;
  p_emaildomain: string | null;
  device_type: string | null;
  device_info: string | null;
  raw_features: Record<string, unknown> | null;
  is_fraud: boolean | null;
  created_at: string;
  predictions: PredictionSummary[];
};

// -------- Helpers --------
const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(n);
const fmtScore = (n: number | null) => (n === null ? "-" : n.toFixed(4));
const fmtDateTime = (iso: string) => new Date(iso).toLocaleString();

function decisionColor(d: string): string {
  if (d === "block") return "text-red-400 bg-red-500/10 border-red-500/30";
  if (d === "review") return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
}

function decisionAccent(d: string): { border: string; glow: string; text: string } {
  if (d === "block") return { border: "border-red-500/50", glow: "shadow-red-500/20", text: "text-red-400" };
  if (d === "review") return { border: "border-amber-500/50", glow: "shadow-amber-500/20", text: "text-amber-400" };
  return { border: "border-emerald-500/50", glow: "shadow-emerald-500/20", text: "text-emerald-400" };
}

// -------- Page --------
export default function TransactionDetailPageWrapper() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">Loading&hellip;</div>}>
      <TransactionDetailPage />
    </Suspense>
  );
}

function TransactionDetailPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const txnId = searchParams.get("id");

  const [txn, setTxn] = useState<TxnDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const load = useCallback(async () => {
    if (!txnId) {
      setError("No transaction ID in URL. Add ?id=XXX to the URL.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api<TxnDetail>(`/api/transactions/${txnId}`);
      setTxn(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      if (err instanceof ApiError && err.status === 404) {
        setError(`Transaction #${txnId} not found`);
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load transaction");
    } finally {
      setLoading(false);
    }
  }, [txnId, router]);

  useEffect(() => {
    load();
  }, [load]);

  const latestPred = txn?.predictions[0];

  return (
    <AppShell
      title={txn ? `Transaction #${txn.id}` : "Transaction"}
      subtitle={txn?.external_id ? `External: ${txn.external_id}` : undefined}
      actions={
        <Link
          href="/transactions"
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm border border-slate-700"
        >
          &larr; Back to list
        </Link>
      }
    >
      {loading && <div className="text-slate-400 text-sm">Loading&hellip;</div>}

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300">
          <div className="font-semibold">{error}</div>
        </div>
      )}

      {txn && !error && (
        <div className="space-y-6">
          {/* Top summary strip */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <SummaryTile label="Amount" value={fmtMoney(txn.amount)} accent="slate" />
            <SummaryTile
              label="Decision"
              value={latestPred?.decision.toUpperCase() ?? "-"}
              accent={latestPred?.decision === "block" ? "red" : latestPred?.decision === "review" ? "amber" : "emerald"}
            />
            <SummaryTile
              label="Calibrated Risk"
              value={fmtScore(latestPred?.calibrated_score ?? null)}
              sub={`raw ${latestPred ? latestPred.raw_score.toFixed(4) : "-"}`}
              accent="amber"
            />
            <SummaryTile
              label="Actual Label"
              value={
                txn.is_fraud === true ? "FRAUD"
                  : txn.is_fraud === false ? "Legit"
                  : "Unknown"
              }
              accent={txn.is_fraud === true ? "red" : "slate"}
            />
          </div>

          {/* Latest prediction card + SHAP */}
          {latestPred ? (
            <div className={`bg-slate-900/60 border ${decisionAccent(latestPred.decision).border} rounded-2xl p-6 shadow-xl ${decisionAccent(latestPred.decision).glow}`}>
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">
                    Latest Prediction
                  </div>
                  <div className="text-xs text-slate-500 font-mono">
                    {latestPred.model_version} &middot; {fmtDateTime(latestPred.created_at)}
                    {latestPred.latency_ms !== null && (
                      <> &middot; {latestPred.latency_ms.toFixed(1)} ms</>
                    )}
                  </div>
                </div>
                <span className={`inline-block px-3 py-1 rounded-lg border text-sm font-bold uppercase tracking-wider ${decisionColor(latestPred.decision)}`}>
                  {latestPred.decision}
                </span>
              </div>

              {/* SHAP explanation */}
              <div>
                <h3 className="text-sm font-semibold text-slate-200 mb-1">
                  Why did the model decide this?
                </h3>
                <div className="text-xs text-slate-500 mb-4">
                  Top-{latestPred.shap_top?.length ?? 0} feature contributions from Stage-1 LightGBM (via <code className="text-red-400">pred_contrib</code>).
                  Red bars push the score <span className="text-red-400 font-semibold">toward fraud</span>,
                  green bars push it <span className="text-emerald-400 font-semibold">toward legit</span>.
                </div>
                {latestPred.shap_top && latestPred.shap_top.length > 0 ? (
                  <ShapWaterfall contributions={latestPred.shap_top} />
                ) : (
                  <div className="text-slate-500 text-sm italic">
                    No SHAP contributions stored for this prediction.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 text-slate-500 text-sm">
              No predictions have been made for this transaction yet.
            </div>
          )}

          {/* Transaction attributes */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Transaction Attributes
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-4 text-sm">
              <Attr label="External ID" value={txn.external_id} mono />
              <Attr label="Transaction DT" value={txn.transaction_dt?.toString() ?? null} mono />
              <Attr label="Product Code" value={txn.product_cd} />
              <Attr label="Card1" value={txn.card1} mono />
              <Attr label="Card4 (brand)" value={txn.card4} />
              <Attr label="Card6 (type)" value={txn.card6} />
              <Attr label="Addr1" value={txn.addr1} mono />
              <Attr label="P Email Domain" value={txn.p_emaildomain} mono />
              <Attr label="Device Type" value={txn.device_type} />
              <Attr label="Device Info" value={txn.device_info} />
              <Attr label="Created" value={fmtDateTime(txn.created_at)} />
            </div>
          </div>

          {/* Prediction history */}
          {txn.predictions.length > 1 && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">
                Prediction History ({txn.predictions.length})
              </h3>
              <table className="w-full text-sm">
                <thead className="text-slate-400 uppercase text-[11px] tracking-wider">
                  <tr>
                    <th className="text-left pb-2">When</th>
                    <th className="text-left pb-2">Version</th>
                    <th className="text-right pb-2">Raw</th>
                    <th className="text-right pb-2">Calibrated</th>
                    <th className="text-left pb-2">Decision</th>
                    <th className="text-right pb-2">Latency</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {txn.predictions.map((p) => (
                    <tr key={p.id}>
                      <td className="py-2 text-slate-300">{fmtDateTime(p.created_at)}</td>
                      <td className="py-2 font-mono text-xs text-slate-400">{p.model_version}</td>
                      <td className="py-2 text-right font-mono">{p.raw_score.toFixed(4)}</td>
                      <td className="py-2 text-right font-mono">{fmtScore(p.calibrated_score)}</td>
                      <td className="py-2">
                        <span className={`inline-block px-2 py-0.5 rounded-md border text-xs font-semibold uppercase tracking-wider ${decisionColor(p.decision)}`}>
                          {p.decision}
                        </span>
                      </td>
                      <td className="py-2 text-right font-mono text-slate-400">
                        {p.latency_ms !== null ? `${p.latency_ms.toFixed(1)} ms` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Raw features (collapsible) */}
          {txn.raw_features && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
              <button
                onClick={() => setShowRaw(!showRaw)}
                className="flex items-center gap-2 text-sm font-semibold text-slate-200 hover:text-white"
              >
                <span>{showRaw ? "▼" : "▶"}</span>
                Raw Features JSON ({Object.keys(txn.raw_features).length} fields)
              </button>
              {showRaw && (
                <pre className="mt-4 bg-slate-950 border border-slate-800 rounded-lg p-4 text-xs text-slate-300 overflow-x-auto max-h-96 overflow-y-auto">
                  {JSON.stringify(txn.raw_features, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </AppShell>
  );
}

// -------- Sub-components --------

function SummaryTile({
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
  const valueColor = {
    slate: "text-slate-100",
    red: "text-red-400",
    amber: "text-amber-400",
    emerald: "text-emerald-400",
  }[accent];

  return (
    <div className={`bg-slate-900/60 border ${border} rounded-2xl p-4`}>
      <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${valueColor}`}>{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1 font-mono">{sub}</div>}
    </div>
  );
}

function Attr({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-0.5 ${mono ? "font-mono text-xs" : ""} text-slate-200`}>
        {value ?? <span className="text-slate-600">&mdash;</span>}
      </div>
    </div>
  );
}

