"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
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

type SparkovLookups = {
  categories: string[];
  genders: string[];
  states: string[];
  top_merchants: string[];
  top_cities: { city: string; state_int: number; city_pop: number; lat: number; long: number }[];
  top_jobs: string[];
};

type SparkovSample = {
  amt: number;
  category: string;
  hour: number;
  day_of_week: number;
  merchant: string;
  city: string;
  state: string;
  gender: string;
  cust_age: number;
  cust_merch_dist_km: number;
  job: string | null;
  zip: number | null;
  city_pop: number | null;
  lat: number | null;
  long: number | null;
  merch_lat: number | null;
  merch_long: number | null;
  cc_num: number | null;
  cc_num_txn_count_before: number | null;
  cc_num_amt_sum_before: number | null;
  cc_num_amt_mean_before: number | null;
  cc_num_seconds_since_prev: number | null;
  is_fraud: number;
  label: string;
};

type AccuracyStats = {
  correct: number;   // block on fraud OR approve on legit
  wrong: number;     // block on legit OR approve on fraud
  reviewed: number;  // decision=review (neutral — sent to human)
};

const ACCURACY_KEY = "chimera_sparkov_accuracy";

function loadAccuracy(): AccuracyStats {
  if (typeof window === "undefined") return { correct: 0, wrong: 0, reviewed: 0 };
  try {
    const s = localStorage.getItem(ACCURACY_KEY);
    if (!s) return { correct: 0, wrong: 0, reviewed: 0 };
    return JSON.parse(s);
  } catch {
    return { correct: 0, wrong: 0, reviewed: 0 };
  }
}

function saveAccuracy(a: AccuracyStats) {
  if (typeof window === "undefined") return;
  try { localStorage.setItem(ACCURACY_KEY, JSON.stringify(a)); } catch {}
}

type FormState = {
  amt: string;
  category: string;
  hour: string;
  day_of_week: string;
  merchant: string;
  city: string;
  state: string;
  gender: string;
  cust_age: string;
  cust_merch_dist_km: string;
  job: string;
  zip: string;
  city_pop: string;
  lat: string;
  long: string;
  merch_lat: string;
  merch_long: string;
  cc_num_txn_count_before: string;
  cc_num_amt_mean_before: string;
};

const EMPTY_FORM: FormState = {
  amt: "",
  category: "grocery_pos",
  hour: "12",
  day_of_week: "2",
  merchant: "",
  city: "",
  state: "IL",
  gender: "M",
  cust_age: "35",
  cust_merch_dist_km: "10",
  job: "",
  zip: "",
  city_pop: "",
  lat: "",
  long: "",
  merch_lat: "",
  merch_long: "",
  cc_num_txn_count_before: "0",
  cc_num_amt_mean_before: "0",
};

// -------- Helpers --------
const fmtScore = (n: number | null) => (n === null ? "-" : n.toFixed(4));

function decisionColor(d: string): string {
  if (d === "block") return "text-red-400 bg-red-500/10 border-red-500/30";
  if (d === "review") return "text-amber-400 bg-amber-500/10 border-amber-500/30";
  return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
}

// -------- Component --------
export function SparkovPredictMode() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [lookups, setLookups] = useState<SparkovLookups | null>(null);
  const [sampleLoaded, setSampleLoaded] = useState<boolean>(false);
  // Blind ground truth — hidden until user clicks Reveal
  const [groundTruth, setGroundTruth] = useState<{ is_fraud: number; merchant: string; city: string } | null>(null);
  const [revealed, setRevealed] = useState<boolean>(false);
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [samplesLoading, setSamplesLoading] = useState(false);
  const [accuracy, setAccuracy] = useState<AccuracyStats>({ correct: 0, wrong: 0, reviewed: 0 });

  useEffect(() => {
    setAccuracy(loadAccuracy());
  }, []);

  function setField(k: keyof FormState, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  // Load dropdown lookups on mount
  const loadLookups = useCallback(async () => {
    try {
      const res = await api<SparkovLookups>("/api/predict/sparkov/lookups");
      setLookups(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      const msg = err instanceof Error ? err.message : "Failed to load Sparkov dropdowns";
      setError(msg);
    }
  }, [router]);

  useEffect(() => {
    loadLookups();
  }, [loadLookups]);

  async function loadRandomSample() {
    setSamplesLoading(true);
    setError(null);
    setResult(null);
    setRevealed(false);
    try {
      // BLIND: server picks 50/50 fraud/legit, UI doesn't reveal label
      const row = await api<SparkovSample>("/api/predict/sparkov/random");
      setForm({
        amt: String(row.amt),
        category: row.category,
        hour: String(row.hour),
        day_of_week: String(row.day_of_week),
        merchant: row.merchant,
        city: row.city,
        state: row.state,
        gender: row.gender,
        cust_age: String(row.cust_age),
        cust_merch_dist_km: String(row.cust_merch_dist_km),
        job: row.job ?? "",
        zip: row.zip !== null ? String(row.zip) : "",
        city_pop: row.city_pop !== null ? String(row.city_pop) : "",
        lat: row.lat !== null ? String(row.lat) : "",
        long: row.long !== null ? String(row.long) : "",
        merch_lat: row.merch_lat !== null ? String(row.merch_lat) : "",
        merch_long: row.merch_long !== null ? String(row.merch_long) : "",
        cc_num_txn_count_before: row.cc_num_txn_count_before !== null ? String(row.cc_num_txn_count_before) : "0",
        cc_num_amt_mean_before: row.cc_num_amt_mean_before !== null ? String(row.cc_num_amt_mean_before) : "0",
      });
      // Store ground truth in state — but the UI won't render the label yet.
      // Only "Reveal ground truth" (after prediction) surfaces it.
      setGroundTruth({ is_fraud: row.is_fraud, merchant: row.merchant, city: row.city });
      setSampleLoaded(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to fetch a random transaction");
    } finally {
      setSamplesLoading(false);
    }
  }

  function clearAll() {
    setForm(EMPTY_FORM);
    setSampleLoaded(false);
    setGroundTruth(null);
    setRevealed(false);
    setResult(null);
    setError(null);
  }

  function revealAndScore() {
    if (!result || !groundTruth) return;
    setRevealed(true);

    // Update running accuracy stats
    const decision = result.decision;
    let bump: Partial<AccuracyStats> = {};
    if (decision === "review") {
      bump = { reviewed: 1 };
    } else if (groundTruth.is_fraud === 1) {
      // Ground truth: fraud
      bump = decision === "block" ? { correct: 1 } : { wrong: 1 };
    } else {
      // Ground truth: legit
      bump = decision === "approve" ? { correct: 1 } : { wrong: 1 };
    }
    const next: AccuracyStats = {
      correct: accuracy.correct + (bump.correct ?? 0),
      wrong: accuracy.wrong + (bump.wrong ?? 0),
      reviewed: accuracy.reviewed + (bump.reviewed ?? 0),
    };
    setAccuracy(next);
    saveAccuracy(next);
  }

  function resetAccuracy() {
    const zero = { correct: 0, wrong: 0, reviewed: 0 };
    setAccuracy(zero);
    saveAccuracy(zero);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setResult(null);

    const body: Record<string, unknown> = {
      amt: parseFloat(form.amt),
      category: form.category,
      hour: parseInt(form.hour, 10),
      day_of_week: parseInt(form.day_of_week, 10),
      merchant: form.merchant,
      city: form.city,
      state: form.state,
      gender: form.gender,
      cust_age: parseInt(form.cust_age, 10),
    };
    if (form.cust_merch_dist_km) body.cust_merch_dist_km = parseFloat(form.cust_merch_dist_km);
    if (form.job) body.job = form.job;
    if (form.zip) body.zip = parseInt(form.zip, 10);
    if (form.city_pop) body.city_pop = parseInt(form.city_pop, 10);
    if (form.lat) body.lat = parseFloat(form.lat);
    if (form.long) body.long = parseFloat(form.long);
    if (form.merch_lat) body.merch_lat = parseFloat(form.merch_lat);
    if (form.merch_long) body.merch_long = parseFloat(form.merch_long);
    if (form.cc_num_txn_count_before) body.cc_num_txn_count_before = parseInt(form.cc_num_txn_count_before, 10);
    if (form.cc_num_amt_mean_before) body.cc_num_amt_mean_before = parseFloat(form.cc_num_amt_mean_before);

    try {
      const res = await api<PredictionResponse>("/api/predict/sparkov", {
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

  const isLookupsReady = lookups !== null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* LEFT — Form */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <h2 className="text-lg font-semibold">Sparkov Transaction</h2>
            {sampleLoaded ? (
              <div className="text-[11px] text-slate-400 mt-0.5 font-mono max-w-md truncate">
                Blind sample loaded · label hidden until reveal
              </div>
            ) : (
              <div className="text-[11px] text-slate-500 mt-0.5">Human-readable fields · 30 model features</div>
            )}
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              disabled={samplesLoading}
              onClick={loadRandomSample}
              className="px-3 py-1 text-xs bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 text-red-400 border border-red-500/30 rounded-lg font-semibold"
            >
              {samplesLoading ? "..." : "Load Random Transaction"}
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

        {!isLookupsReady && (
          <div className="text-xs text-amber-400 mb-3 border border-amber-500/30 bg-amber-500/10 rounded-lg px-3 py-2">
            Loading Sparkov dropdowns from backend&hellip;
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Required */}
          <div>
            <div className="text-xs uppercase tracking-wider text-red-500 font-bold mb-2">
              Transaction basics
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Amount (USD)" required>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  required
                  value={form.amt}
                  onChange={(e) => setField("amt", e.target.value)}
                  placeholder="107.23"
                  className={inputCls}
                />
              </Field>
              <Field label="Merchant Category" required>
                <select
                  value={form.category}
                  onChange={(e) => setField("category", e.target.value)}
                  className={inputCls}
                >
                  {(lookups?.categories ?? ["grocery_pos"]).map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field label="Merchant Name" required>
                <input
                  list="sparkov-merchants"
                  type="text"
                  required
                  value={form.merchant}
                  onChange={(e) => setField("merchant", e.target.value)}
                  placeholder="fraud_Kirlin and Sons"
                  className={inputCls}
                />
                <datalist id="sparkov-merchants">
                  {(lookups?.top_merchants ?? []).map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </Field>
              <Field label="Hour of day (0-23)" required>
                <input
                  type="number"
                  min="0"
                  max="23"
                  required
                  value={form.hour}
                  onChange={(e) => setField("hour", e.target.value)}
                  className={inputCls}
                />
              </Field>
            </div>
          </div>

          {/* Customer */}
          <div>
            <div className="text-xs uppercase tracking-wider text-red-500 font-bold mb-2">
              Cardholder
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="City" required>
                <input
                  list="sparkov-cities"
                  type="text"
                  required
                  value={form.city}
                  onChange={(e) => setField("city", e.target.value)}
                  placeholder="Springfield"
                  className={inputCls}
                />
                <datalist id="sparkov-cities">
                  {(lookups?.top_cities ?? []).map((c) => (
                    <option key={c.city} value={c.city} />
                  ))}
                </datalist>
              </Field>
              <Field label="State (2-letter)" required>
                <select
                  value={form.state}
                  onChange={(e) => setField("state", e.target.value)}
                  className={inputCls}
                >
                  {(lookups?.states ?? ["IL"]).map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </Field>
              <Field label="Age" required>
                <input
                  type="number"
                  min="0"
                  max="120"
                  required
                  value={form.cust_age}
                  onChange={(e) => setField("cust_age", e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="Gender" required>
                <select
                  value={form.gender}
                  onChange={(e) => setField("gender", e.target.value)}
                  className={inputCls}
                >
                  <option value="F">F</option>
                  <option value="M">M</option>
                </select>
              </Field>
              <Field label="Job">
                <input
                  list="sparkov-jobs"
                  type="text"
                  value={form.job}
                  onChange={(e) => setField("job", e.target.value)}
                  placeholder="Software Engineer"
                  className={inputCls}
                />
                <datalist id="sparkov-jobs">
                  {(lookups?.top_jobs ?? []).map((j) => (
                    <option key={j} value={j} />
                  ))}
                </datalist>
              </Field>
              <Field label="Day of week (0=Mon)">
                <input
                  type="number"
                  min="0"
                  max="6"
                  value={form.day_of_week}
                  onChange={(e) => setField("day_of_week", e.target.value)}
                  className={inputCls}
                />
              </Field>
            </div>
          </div>

          {/* Advanced */}
          <details className="group">
            <summary className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2 cursor-pointer hover:text-slate-300">
              Advanced (geography, velocity)
            </summary>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <Field label="Cust ↔ Merchant distance (km)">
                <input
                  type="number"
                  step="0.1"
                  value={form.cust_merch_dist_km}
                  onChange={(e) => setField("cust_merch_dist_km", e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="City population">
                <input
                  type="number"
                  value={form.city_pop}
                  onChange={(e) => setField("city_pop", e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="Zip">
                <input
                  type="number"
                  value={form.zip}
                  onChange={(e) => setField("zip", e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="Prior transaction count">
                <input
                  type="number"
                  value={form.cc_num_txn_count_before}
                  onChange={(e) => setField("cc_num_txn_count_before", e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="Customer avg past amt">
                <input
                  type="number"
                  step="0.01"
                  value={form.cc_num_amt_mean_before}
                  onChange={(e) => setField("cc_num_amt_mean_before", e.target.value)}
                  className={inputCls}
                />
              </Field>
            </div>
          </details>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-gradient-to-br from-red-500 to-red-700 hover:from-red-600 hover:to-red-800 disabled:opacity-50 text-white font-semibold text-sm shadow-lg shadow-red-500/20"
          >
            {loading ? "Scoring…" : "Score Transaction"}
          </button>
        </form>
      </div>

      {/* RIGHT — Result + Accuracy tracker */}
      <div className="space-y-4">
        {/* Running accuracy scoreboard */}
        <AccuracyBoard stats={accuracy} onReset={resetAccuracy} />

        {!result && !loading && !error && (
          <EmptyState sampleLoaded={sampleLoaded} />
        )}

        {loading && (
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center">
            <div className="text-slate-400">Scoring Sparkov transaction&hellip;</div>
            <div className="text-xs text-slate-500 mt-2">Building 30 features · Sparkov LightGBM · SHAP top-5</div>
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6 text-red-300">
            <div className="font-semibold">Prediction failed</div>
            <div className="text-sm mt-1">{error}</div>
          </div>
        )}

        {result && (
          <div className={`bg-slate-900/60 border rounded-2xl p-6 shadow-lg ${decisionColor(result.decision)}`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-[10px] uppercase tracking-widest opacity-60 font-bold">Model decision</div>
                <div className="text-3xl font-black uppercase mt-1" style={{ fontFamily: "var(--font-serif)" }}>
                  {result.decision}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-widest opacity-60 font-bold">Risk score</div>
                <div className="text-3xl font-mono font-bold mt-1">{fmtScore(result.calibrated_score)}</div>
                <div className="text-[10px] opacity-60 mt-0.5">raw = {fmtScore(result.raw_score)}</div>
              </div>
            </div>

            {/* Ground truth reveal — only if sample was loaded */}
            {groundTruth && (
              <div className="border-t border-current/20 pt-4 mt-4">
                {!revealed ? (
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="text-[11px] opacity-80">
                      <div className="font-bold uppercase tracking-wider">Blind test</div>
                      <div className="opacity-70">Ground truth is stored but hidden. Guess before revealing.</div>
                    </div>
                    <button
                      type="button"
                      onClick={revealAndScore}
                      className="px-3 py-1.5 text-xs font-bold rounded-lg bg-white/10 hover:bg-white/20 border border-current/30 transition"
                    >
                      Reveal ground truth →
                    </button>
                  </div>
                ) : (
                  <GroundTruthPanel
                    isFraud={groundTruth.is_fraud === 1}
                    decision={result.decision}
                  />
                )}
              </div>
            )}

            <div className="border-t border-current/20 pt-4 mt-4">
              <div className="text-[10px] uppercase tracking-widest opacity-60 font-bold mb-3">
                SHAP · Top feature contributions
              </div>
              <ShapWaterfall contributions={result.shap_top} />
            </div>

            <div className="mt-4 flex gap-3 text-[10px] opacity-60 flex-wrap">
              <span>#{result.transaction_id}</span>
              <span>·</span>
              <span>{result.latency_ms.toFixed(1)}&nbsp;ms</span>
              <span>·</span>
              <span className="font-mono truncate">{result.model_version.slice(0, 30)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// -------- Local helpers --------
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

function EmptyState({ sampleLoaded }: { sampleLoaded: boolean }) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-slate-600 mb-4">
        <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.5 8.5 2.2 2.2M5.6 18.4l2.1-2.1m8.5-8.5 2.2-2.2" />
        <circle cx="12" cy="12" r="4" />
      </svg>
      <div className="text-slate-300 font-semibold mb-1">
        {sampleLoaded ? "Look at the input — do you think it's fraud?" : "Blind fraud test"}
      </div>
      <div className="text-sm text-slate-500 max-w-xs">
        {sampleLoaded
          ? "Study the amount, merchant, hour, distance. Make your guess. Then click Score Transaction and Reveal the ground truth."
          : "Click Load Random Transaction to draw a real, unlabeled transaction from 185K test samples. Model has never seen it before."}
      </div>
      <div className="mt-4 flex gap-2 text-xs text-slate-500 flex-wrap justify-center">
        <span className="px-2 py-1 bg-slate-800 rounded">Sparkov LightGBM</span>
        <span className="px-2 py-1 bg-slate-800 rounded">ROC-AUC 0.97</span>
        <span className="px-2 py-1 bg-slate-800 rounded">SHAP top-5</span>
      </div>
    </div>
  );
}

function AccuracyBoard({ stats, onReset }: { stats: AccuracyStats; onReset: () => void }) {
  const total = stats.correct + stats.wrong;
  const acc = total > 0 ? (stats.correct / total) * 100 : null;
  const anyData = total > 0 || stats.reviewed > 0;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-[10px] uppercase tracking-widest font-bold text-slate-400">Blind Test Scoreboard</div>
          <div className="text-[11px] text-slate-500 mt-0.5">Persists across page reloads · reveal after each score</div>
        </div>
        {anyData && (
          <button
            type="button"
            onClick={onReset}
            className="text-[10px] text-slate-500 hover:text-slate-300 underline"
          >
            reset
          </button>
        )}
      </div>
      <div className="grid grid-cols-4 gap-2">
        <div className="bg-slate-950/50 rounded-lg p-2 text-center">
          <div className="text-[9px] uppercase tracking-wider text-slate-500 font-bold">Accuracy</div>
          <div className="text-lg font-mono font-bold text-white mt-0.5">
            {acc === null ? "—" : `${acc.toFixed(0)}%`}
          </div>
        </div>
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2 text-center">
          <div className="text-[9px] uppercase tracking-wider text-emerald-400 font-bold">Correct</div>
          <div className="text-lg font-mono font-bold text-emerald-300 mt-0.5">{stats.correct}</div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
          <div className="text-[9px] uppercase tracking-wider text-red-400 font-bold">Wrong</div>
          <div className="text-lg font-mono font-bold text-red-300 mt-0.5">{stats.wrong}</div>
        </div>
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 text-center">
          <div className="text-[9px] uppercase tracking-wider text-amber-400 font-bold">Reviewed</div>
          <div className="text-lg font-mono font-bold text-amber-300 mt-0.5">{stats.reviewed}</div>
        </div>
      </div>
    </div>
  );
}

function GroundTruthPanel({ isFraud, decision }: { isFraud: boolean; decision: string }) {
  const isReview = decision === "review";
  let verdict: { label: string; color: string; icon: string };

  if (isReview) {
    verdict = {
      label: "Sent to human review — no auto-call",
      color: "text-amber-300 bg-amber-500/10 border-amber-500/30",
      icon: "≈",
    };
  } else if ((isFraud && decision === "block") || (!isFraud && decision === "approve")) {
    verdict = {
      label: `Model correct — caught ${isFraud ? "fraud" : "legit"}`,
      color: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
      icon: "✓",
    };
  } else {
    verdict = {
      label: isFraud ? "Missed fraud — model approved a real fraud" : "False positive — model blocked a legit txn",
      color: "text-red-300 bg-red-500/10 border-red-500/30",
      icon: "✗",
    };
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2 gap-3 flex-wrap">
        <div className="text-[10px] uppercase tracking-widest opacity-80 font-bold">Ground truth (revealed)</div>
        <div className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
          isFraud ? "bg-red-500/20 text-red-300 border-red-500/40" : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
        }`}>
          Actually {isFraud ? "FRAUD" : "LEGIT"}
        </div>
      </div>
      <div className={`text-xs px-3 py-2 rounded-lg border font-semibold ${verdict.color} flex items-center gap-2`}>
        <span className="text-lg leading-none">{verdict.icon}</span>
        {verdict.label}
      </div>
    </div>
  );
}
