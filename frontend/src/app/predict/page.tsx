"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";
import { ShapWaterfall, ShapContribution } from "@/components/ShapWaterfall";

// -------- Types --------
type PredictionResponse = {
  transaction_id: number;
  prediction_id: number;
  raw_score: number;
  calibrated_score: number | null;
  decision: string;
  shap_top: ShapContribution[];
  model_version: string;
  latency_ms: number;
  created_at: string;
};

type FormState = {
  TransactionAmt: string;
  ProductCD: string;
  TransactionDT: string;
  card1: string;
  card4: string;
  card6: string;
  addr1: string;
  P_emaildomain: string;
  DeviceType: string;
  DeviceInfo: string;
};

type SampleRow = Record<string, unknown>;

type SamplesResponse = {
  risky: SampleRow | null;
  legit: SampleRow | null;
  pool_sizes: { fraud: number; legit: number };
};

const CORE_FORM_FIELDS = [
  "TransactionAmt", "ProductCD", "TransactionDT",
  "card1", "card4", "card6",
  "addr1", "P_emaildomain",
  "DeviceType", "DeviceInfo",
] as const;

function rowToForm(row: SampleRow): FormState {
  const s = (k: string) => {
    const v = row[k];
    if (v === null || v === undefined) return "";
    return String(v);
  };
  return {
    TransactionAmt: s("TransactionAmt"),
    ProductCD: s("ProductCD") || "W",
    TransactionDT: s("TransactionDT") || "86400",
    card1: s("card1"),
    card4: s("card4"),
    card6: s("card6"),
    addr1: s("addr1"),
    P_emaildomain: s("P_emaildomain"),
    DeviceType: s("DeviceType"),
    DeviceInfo: s("DeviceInfo"),
  };
}

function rowToExtras(row: SampleRow): Record<string, unknown> {
  // Include EVERYTHING from the parquet row except pure metadata.
  // Categorical form fields (ProductCD, card4, card6, DeviceType) are stored
  // in the parquet as label-encoded integers — we must send those integer
  // versions in extras so they override the form's string values on the
  // backend (payload.as_raw_dict() applies extras on top of top-level fields).
  const skip = new Set<string>([
    "isFraud", "TransactionID", "external_id",
  ]);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) {
    if (skip.has(k)) continue;
    if (v === null || v === undefined) continue;
    out[k] = v;
  }
  return out;
}

const EMPTY: FormState = {
  TransactionAmt: "",
  ProductCD: "W",
  TransactionDT: "86400",
  card1: "",
  card4: "",
  card6: "",
  addr1: "",
  P_emaildomain: "",
  DeviceType: "",
  DeviceInfo: "",
};

// -------- Helpers --------
const fmtScore = (n: number | null) => (n === null ? "-" : n.toFixed(4));
const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(n);

function decisionColor(d: string): string {
  if (d === "block") return "text-red-400 bg-red-500/10 border-red-500/30";
  if (d === "review") return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
}

// -------- Page --------
export default function PredictPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [extras, setExtras] = useState<Record<string, unknown> | null>(null);
  const [sampleLabel, setSampleLabel] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [samplesLoading, setSamplesLoading] = useState(false);

  function setField(k: keyof FormState, v: string) {
    setForm({ ...form, [k]: v });
  }

  async function loadSample(kind: "risky" | "legit") {
    setSamplesLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api<SamplesResponse>("/api/predict/samples");
      const row = kind === "risky" ? res.risky : res.legit;
      if (!row) {
        setError(`No ${kind} sample available on server. Try seeding data first.`);
        return;
      }
      setForm(rowToForm(row));
      setExtras(rowToExtras(row));
      setSampleLabel(
        kind === "risky"
          ? `Real FRAUD row from IEEE-CIS (${Object.keys(row).length} features)`
          : `Real LEGIT row from IEEE-CIS (${Object.keys(row).length} features)`
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to fetch samples");
    } finally {
      setSamplesLoading(false);
    }
  }

  function clearAll() {
    setForm(EMPTY);
    setExtras(null);
    setSampleLabel(null);
    setResult(null);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setResult(null);

    // Build request body — form fields + extras (V*, C*, D*, id_*)
    const body: Record<string, unknown> = {
      TransactionAmt: parseFloat(form.TransactionAmt),
      TransactionDT: parseInt(form.TransactionDT, 10),
    };
    if (form.ProductCD) body.ProductCD = form.ProductCD;
    if (form.card1) body.card1 = parseInt(form.card1, 10);
    if (form.card4) body.card4 = form.card4;
    if (form.card6) body.card6 = form.card6;
    if (form.addr1) body.addr1 = parseFloat(form.addr1);
    if (form.P_emaildomain) body.P_emaildomain = form.P_emaildomain;
    if (form.DeviceType) body.DeviceType = form.DeviceType;
    if (form.DeviceInfo) body.DeviceInfo = form.DeviceInfo;

    if (extras && Object.keys(extras).length > 0) {
      body.extras = extras;
    }

    try {
      const res = await api<PredictionResponse>("/api/predict", {
        method: "POST",
        body,
      });
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to score transaction");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell
      title="Live Predict"
      subtitle="Score a single transaction against the deployed Stage-1 model"
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT: Form */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold">Transaction Input</h2>
              {sampleLabel && (
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                  {sampleLabel}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={samplesLoading}
                onClick={() => loadSample("legit")}
                className="px-3 py-1 text-xs bg-emerald-500/10 hover:bg-emerald-500/20 disabled:opacity-50 text-emerald-400 border border-emerald-500/30 rounded-lg"
              >
                {samplesLoading ? "..." : "Load Legit Sample"}
              </button>
              <button
                type="button"
                disabled={samplesLoading}
                onClick={() => loadSample("risky")}
                className="px-3 py-1 text-xs bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 text-red-400 border border-red-500/30 rounded-lg"
              >
                {samplesLoading ? "..." : "Load Risky Sample"}
              </button>
              <button
                type="button"
                onClick={clearAll}
                className="px-3 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-400 border border-slate-700 rounded-lg"
              >
                Clear
              </button>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Required section */}
            <div>
              <div className="text-xs uppercase tracking-wider text-red-500 font-bold mb-2">
                Required
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Amount (USD)" required>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={form.TransactionAmt}
                    onChange={(e) => setField("TransactionAmt", e.target.value)}
                    placeholder="59.95"
                    className={inputCls}
                  />
                </Field>
                <Field label="Product Code">
                  <select
                    value={form.ProductCD}
                    onChange={(e) => setField("ProductCD", e.target.value)}
                    className={inputCls}
                  >
                    <option value="W">W (web)</option>
                    <option value="C">C (in-store)</option>
                    <option value="H">H</option>
                    <option value="R">R</option>
                    <option value="S">S</option>
                  </select>
                </Field>
              </div>
            </div>

            {/* Card details */}
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">
                Card Details
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Field label="Card1 (issuer)">
                  <input
                    type="number"
                    value={form.card1}
                    onChange={(e) => setField("card1", e.target.value)}
                    placeholder="6019"
                    className={inputCls}
                  />
                </Field>
                <Field label="Card4 (brand)">
                  <select
                    value={form.card4}
                    onChange={(e) => setField("card4", e.target.value)}
                    className={inputCls}
                  >
                    <option value="">-</option>
                    <option value="visa">visa</option>
                    <option value="mastercard">mastercard</option>
                    <option value="american express">amex</option>
                    <option value="discover">discover</option>
                  </select>
                </Field>
                <Field label="Card6 (type)">
                  <select
                    value={form.card6}
                    onChange={(e) => setField("card6", e.target.value)}
                    className={inputCls}
                  >
                    <option value="">-</option>
                    <option value="debit">debit</option>
                    <option value="credit">credit</option>
                  </select>
                </Field>
              </div>
            </div>

            {/* Customer / device */}
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">
                Customer &amp; Device
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Address (addr1)">
                  <input
                    type="number"
                    value={form.addr1}
                    onChange={(e) => setField("addr1", e.target.value)}
                    placeholder="315"
                    className={inputCls}
                  />
                </Field>
                <Field label="Email Domain">
                  <input
                    type="text"
                    value={form.P_emaildomain}
                    onChange={(e) => setField("P_emaildomain", e.target.value)}
                    placeholder="gmail.com"
                    className={inputCls}
                  />
                </Field>
                <Field label="Device Type">
                  <select
                    value={form.DeviceType}
                    onChange={(e) => setField("DeviceType", e.target.value)}
                    className={inputCls}
                  >
                    <option value="">-</option>
                    <option value="desktop">desktop</option>
                    <option value="mobile">mobile</option>
                  </select>
                </Field>
                <Field label="Device Info">
                  <input
                    type="text"
                    value={form.DeviceInfo}
                    onChange={(e) => setField("DeviceInfo", e.target.value)}
                    placeholder="Windows"
                    className={inputCls}
                  />
                </Field>
              </div>
            </div>

            {/* Extras indicator */}
            {extras && Object.keys(extras).length > 0 && (
              <div className="text-[11px] text-slate-500 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2">
                <span className="text-emerald-400">&#10003;</span> Sending{" "}
                <span className="text-slate-300 font-mono">{Object.keys(extras).length}</span>{" "}
                additional features (V*, C*, D*, id_*) as{" "}
                <code className="text-red-400">extras</code>. Full 456-feature scoring.
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !form.TransactionAmt}
              className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:opacity-60 text-white font-semibold py-3 rounded-lg transition mt-2"
            >
              {loading ? "Scoring..." : "Score Transaction"}
            </button>
          </form>
        </div>

        {/* RIGHT: Result panel */}
        <div>
          {!result && !loading && !error && (
            <EmptyState />
          )}

          {loading && (
            <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center">
              <div className="text-slate-400">Scoring transaction&hellip;</div>
              <div className="text-xs text-slate-500 mt-2">Building features &rarr; Stage 1 LightGBM &rarr; Isotonic calibration &rarr; SHAP</div>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6 text-red-300">
              <div className="font-semibold">Prediction failed</div>
              <div className="text-sm mt-1">{error}</div>
            </div>
          )}

          {result && (
            <ResultPanel result={result} />
          )}
        </div>
      </div>
    </AppShell>
  );
}

// -------- Sub-components --------

const inputCls =
  "w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-red-500";

function Field({
  label, required, children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wider text-slate-400">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function EmptyState() {
  return (
    <div className="bg-slate-900/60 border border-slate-800 border-dashed rounded-2xl p-8 h-full flex flex-col items-center justify-center text-center">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-600 mb-4">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
      <div className="text-slate-300 font-semibold mb-1">No transaction scored yet</div>
      <div className="text-sm text-slate-500 max-w-xs">
        Fill the form on the left and click <span className="text-slate-300">Score Transaction</span>{" "}
        to see the model decision, calibrated risk score, and SHAP feature contributions in under
        100&nbsp;ms.
      </div>
      <div className="mt-4 flex gap-2 text-xs text-slate-500">
        <span className="px-2 py-1 bg-slate-800 rounded">Stage 1 LightGBM</span>
        <span className="px-2 py-1 bg-slate-800 rounded">Isotonic Calibration</span>
        <span className="px-2 py-1 bg-slate-800 rounded">SHAP top-5</span>
      </div>
    </div>
  );
}

function ResultPanel({ result }: { result: PredictionResponse }) {
  const isBlock = result.decision === "block";
  const isReview = result.decision === "review";
  const isApprove = result.decision === "approve";
  const border = isBlock ? "border-red-500/50" : isReview ? "border-amber-500/50" : "border-emerald-500/50";
  const glow = isBlock ? "shadow-red-500/20" : isReview ? "shadow-amber-500/20" : "shadow-emerald-500/20";

  return (
    <div className={`bg-slate-900/60 border-2 ${border} rounded-2xl p-6 shadow-2xl ${glow}`}>
      {/* Decision */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">
            Model Decision
          </div>
          <div className={`text-3xl font-bold ${isBlock ? "text-red-400" : isReview ? "text-amber-400" : "text-emerald-400"}`}>
            {result.decision.toUpperCase()}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wider text-slate-400 mb-1">
            Scoring Latency
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {result.latency_ms.toFixed(1)}<span className="text-sm text-slate-400 ml-1">ms</span>
          </div>
        </div>
      </div>

      {/* Score details */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <ScoreTile label="Calibrated Risk" value={fmtScore(result.calibrated_score)} highlight />
        <ScoreTile label="Raw Score" value={result.raw_score.toFixed(4)} />
        <ScoreTile label="Confidence" value={confidenceLabel(result)} textColor={confidenceColor(result)} />
      </div>

      {/* Model version */}
      <div className="text-xs text-slate-500 font-mono mb-4">
        Model: {result.model_version} &middot; Saved as{" "}
        <Link href={`/transaction?id=${result.transaction_id}`} className="text-red-400 hover:underline">
          transaction #{result.transaction_id}
        </Link>
      </div>

      {/* SHAP */}
      <div className="pt-4 border-t border-slate-800">
        <h3 className="text-sm font-semibold text-slate-200 mb-1">
          Why did the model decide this?
        </h3>
        <div className="text-xs text-slate-500 mb-4">
          Top-{result.shap_top.length} feature contributions from Stage-1 LightGBM.
          Red bars push <span className="text-red-400 font-semibold">toward fraud</span>,
          green bars push <span className="text-emerald-400 font-semibold">toward legit</span>.
        </div>
        <ShapWaterfall contributions={result.shap_top} />
      </div>
    </div>
  );
}

function ScoreTile({
  label, value, highlight, textColor,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  textColor?: string;
}) {
  return (
    <div className={`bg-slate-950 border ${highlight ? "border-slate-600" : "border-slate-800"} rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-xl font-bold mt-1 font-mono ${textColor ?? "text-slate-100"}`}>{value}</div>
    </div>
  );
}

function confidenceLabel(r: PredictionResponse): string {
  const s = r.calibrated_score ?? r.raw_score;
  if (s < 0.05) return "Very Low";
  if (s < 0.2) return "Low";
  if (s < 0.5) return "Medium";
  if (s < 0.8) return "High";
  return "Very High";
}

function confidenceColor(r: PredictionResponse): string {
  const s = r.calibrated_score ?? r.raw_score;
  if (s < 0.05) return "text-emerald-400";
  if (s < 0.2) return "text-emerald-300";
  if (s < 0.5) return "text-amber-400";
  if (s < 0.8) return "text-red-400";
  return "text-red-500";
}
