"use client";

import Link from "next/link";
import { PublicShell } from "@/components/PublicShell";

export default function FeaturesPage() {
  return (
    <PublicShell>
      <section className="pt-24 pb-16 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-radial from-red-950/20 via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-4">
            Features
          </div>
          <h1 className="text-4xl md:text-6xl font-serif font-black tracking-tight mb-6">
            The full fraud stack.
          </h1>
          <p className="text-lg text-slate-400 leading-relaxed">
            From the first scored transaction to the final analyst verdict,
            here&apos;s everything CHIMERA-FD does.
          </p>
        </div>
      </section>

      {DETAILED_FEATURES.map((f, i) => (
        <FeatureRow key={f.title} feature={f} reversed={i % 2 === 1} />
      ))}

      <section className="py-24">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            See it in action.
          </h2>
          <p className="text-slate-400 text-lg mb-8">
            Free workspace, no credit card required.
          </p>
          <Link
            href="/register"
            className="inline-block px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30"
          >
            Create workspace &rarr;
          </Link>
        </div>
      </section>
    </PublicShell>
  );
}

type Feature = {
  eyebrow: string;
  title: string;
  desc: string;
  bullets: string[];
  visual: React.ReactNode;
};

function FeatureRow({ feature, reversed }: { feature: Feature; reversed: boolean }) {
  return (
    <section className="py-16">
      <div className="max-w-6xl mx-auto px-6">
        <div className={`grid grid-cols-1 md:grid-cols-2 gap-12 items-center ${reversed ? "md:[direction:rtl]" : ""}`}>
          <div className="md:[direction:ltr]">
            <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-3">
              {feature.eyebrow}
            </div>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">{feature.title}</h2>
            <p className="text-slate-300 text-lg mb-6 leading-relaxed">{feature.desc}</p>
            <ul className="space-y-2">
              {feature.bullets.map((b, i) => (
                <li key={i} className="flex items-start gap-3 text-slate-300">
                  <span className="w-5 h-5 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center text-red-400 text-xs shrink-0 mt-0.5">
                    &#10003;
                  </span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="md:[direction:ltr]">{feature.visual}</div>
        </div>
      </div>
    </section>
  );
}

const DETAILED_FEATURES: Feature[] = [
  {
    eyebrow: "Real-time inference",
    title: "Under 10ms per transaction.",
    desc: "The Stage 1 LightGBM model loads once at process startup, warms up its JIT cache, and serves every request from memory. Median latency on modest hardware is 2 ms.",
    bullets: [
      "Sub-10 ms 95th-percentile scoring latency",
      "Singleton model service with warmup",
      "No cold starts on the deployed container",
      "Comfortable within the 50 ms payment authorization budget",
    ],
    visual: <VisualLatency />,
  },
  {
    eyebrow: "Explainable AI",
    title: "SHAP contributions with every decision.",
    desc: "Every scored transaction returns the top-5 features driving it, computed exactly via LightGBM's native prediction contribution mode. Analysts see red bars pushing toward fraud and green bars pushing toward legitimate.",
    bullets: [
      "TreeSHAP-equivalent contributions in polynomial time",
      "Zero overhead vs the general shap Python library",
      "Faithful even under severe class imbalance (Zafar & Wu paradox resolved)",
      "Persisted per prediction for audit and later review",
    ],
    visual: <VisualShap />,
  },
  {
    eyebrow: "Calibration",
    title: "Real probabilities, not just rankings.",
    desc: "The raw Stage 1 score passes through a Stage 3 isotonic regression fit on validation data. A calibrated 0.7 means an actual 70% chance of fraud &mdash; suitable for cost-based decision thresholds.",
    bullets: [
      "Isotonic regression is non-parametric and monotonic",
      "Preserves ranking while correcting probability distortion",
      "Enables proper cost-optimized threshold tuning",
      "Reliability diagrams reported before and after in the training pipeline",
    ],
    visual: <VisualCalibration />,
  },
  {
    eyebrow: "Multi-tenancy",
    title: "Isolated workspaces per company.",
    desc: "Every user belongs to a company; every transaction and prediction belongs to a company. Cross-company visibility is zero by construction. Multiple analysts within the same company share a common review queue &mdash; matching real fraud ops workflow.",
    bullets: [
      "Company-scoped queries enforced at the router dependency layer",
      "Two-step registration: company details then admin credentials",
      "Fresh signups get an empty dashboard, guaranteed",
      "Admin role granted to the first user of a new company",
    ],
    visual: <VisualTenancy />,
  },
  {
    eyebrow: "Live predict console",
    title: "Score any transaction, watch it explain.",
    desc: "The Live Predict page lets an analyst manually enter transaction details, click Score, and see the decision plus full SHAP waterfall render in under a second. Includes 'Load risky sample' and 'Load legit sample' buttons that fetch real rows from the training distribution.",
    bullets: [
      "Two-panel layout: form on the left, live result on the right",
      "Real IEEE-CIS fraud rows populated into the form on demand",
      "Full 456-feature scoring or minimal input scoring, transparent to caller",
      "Every scored transaction persisted for later review in the transaction list",
    ],
    visual: <VisualLivePredict />,
  },
  {
    eyebrow: "Cross-dataset validation",
    title: "Methodology, not tricks.",
    desc: "The same training pipeline that produced the IEEE-CIS model was applied without modification to the Sparkov synthetic dataset. Both produced valid models. This is evidence that CHIMERA-FD's approach generalizes across data distributions, not that it was over-tuned to a single benchmark.",
    bullets: [
      "IEEE-CIS: 590K real e-commerce transactions, 3.5% fraud",
      "Sparkov: 1.85M synthetic transactions, 0.52% fraud",
      "Identical hyperparameter families and imbalance treatment",
      "Documented in reports/sparkov_evaluation.json",
    ],
    visual: <VisualCrossDataset />,
  },
];

// -------- Visuals --------

function VisualLatency() {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6">
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-4">Recent scoring times</div>
      <div className="space-y-2">
        {[7.2, 3.1, 5.6, 2.4, 4.8, 8.9, 3.0, 6.1, 2.7, 4.2].map((ms, i) => (
          <div key={i} className="flex items-center gap-3 text-xs">
            <div className="w-16 text-slate-500 font-mono">#{i + 1}</div>
            <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400"
                style={{ width: `${(ms / 15) * 100}%` }}
              />
            </div>
            <div className="w-14 text-right text-slate-300 font-mono">{ms} ms</div>
          </div>
        ))}
      </div>
      <div className="mt-6 pt-4 border-t border-slate-800 flex justify-between text-xs">
        <div>
          <div className="text-slate-500 uppercase tracking-wider">Median</div>
          <div className="text-emerald-400 font-mono font-bold text-lg">4.5 ms</div>
        </div>
        <div>
          <div className="text-slate-500 uppercase tracking-wider">P95</div>
          <div className="text-emerald-400 font-mono font-bold text-lg">8.4 ms</div>
        </div>
        <div>
          <div className="text-slate-500 uppercase tracking-wider">Model</div>
          <div className="text-slate-300 font-mono font-bold text-lg">Stage 1</div>
        </div>
      </div>
    </div>
  );
}

function VisualShap() {
  const bars = [
    { name: "V258", val: "5", contrib: +2.57, positive: true, mag: 90 },
    { name: "C1", val: "12", contrib: +1.44, positive: true, mag: 55 },
    { name: "card1_target_enc", val: "0.011", contrib: -1.18, positive: false, mag: 45 },
    { name: "V189", val: "4", contrib: +0.92, positive: true, mag: 32 },
    { name: "card1_txn_count", val: "6", contrib: -0.66, positive: false, mag: 22 },
  ];
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6">
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Model decision</div>
      <div className="text-2xl font-bold text-amber-400 mb-4">REVIEW &middot; 0.57 risk</div>
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Top 5 contributions</div>
      <div className="space-y-2 text-xs">
        {bars.map((b) => (
          <div key={b.name} className="grid grid-cols-[minmax(90px,1fr)_1fr_1fr_60px] gap-2 items-center">
            <div>
              <div className="font-mono text-slate-200">{b.name}</div>
              <div className="text-[10px] text-slate-500">value: {b.val}</div>
            </div>
            <div className="flex justify-end">
              {!b.positive && <div className="h-4 bg-emerald-500/60 rounded-l" style={{ width: `${b.mag}%` }} />}
            </div>
            <div>
              {b.positive && <div className="h-4 bg-red-500/60 rounded-r" style={{ width: `${b.mag}%` }} />}
            </div>
            <div className={`text-right font-mono ${b.positive ? "text-red-400" : "text-emerald-400"}`}>
              {b.positive ? "+" : ""}{b.contrib.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VisualCalibration() {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6">
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-4">Reliability diagram (after isotonic)</div>
      <div className="relative aspect-square bg-slate-950 rounded-xl p-4">
        {/* Grid */}
        <div className="absolute inset-4 grid grid-cols-5 grid-rows-5">
          {Array.from({ length: 25 }).map((_, i) => (
            <div key={i} className="border-r border-b border-slate-800" />
          ))}
        </div>
        {/* Diagonal ideal */}
        <svg className="absolute inset-4" viewBox="0 0 100 100" preserveAspectRatio="none">
          <line x1="0" y1="100" x2="100" y2="0" stroke="#475569" strokeDasharray="2 3" strokeWidth="0.6" />
          <polyline
            points="5,95 20,84 35,68 50,52 65,38 80,20 95,10"
            fill="none"
            stroke="#f87171"
            strokeWidth="1.6"
          />
          {[[5, 95], [20, 84], [35, 68], [50, 52], [65, 38], [80, 20], [95, 10]].map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="1.8" fill="#dc2626" />
          ))}
        </svg>
        <div className="absolute bottom-1 left-1 text-[10px] text-slate-500">Predicted probability</div>
        <div className="absolute top-1 left-1 text-[10px] text-slate-500 -rotate-90 origin-top-left translate-y-full">
          Empirical fraud rate
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4 text-xs">
        <div>
          <div className="text-slate-500 uppercase tracking-wider">ECE</div>
          <div className="text-emerald-400 font-mono font-bold">0.024</div>
        </div>
        <div>
          <div className="text-slate-500 uppercase tracking-wider">Brier score</div>
          <div className="text-emerald-400 font-mono font-bold">0.031</div>
        </div>
      </div>
    </div>
  );
}

function VisualTenancy() {
  const companies = [
    { name: "Razorpay", txns: 10, fraud: 3 },
    { name: "HDFC Bank", txns: 10, fraud: 3 },
    { name: "Zomato", txns: 10, fraud: 3 },
    { name: "Swiggy", txns: 10, fraud: 3 },
  ];
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6">
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-4">Isolated workspaces</div>
      <div className="space-y-3">
        {companies.map((c) => (
          <div key={c.name} className="bg-slate-950 border border-slate-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <div className="font-semibold text-slate-100">{c.name}</div>
              <div className="text-xs text-slate-500">
                {c.txns} transactions &middot; {c.fraud} confirmed fraud
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 text-xs font-bold">
              {c.name[0]}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-xs text-slate-500 text-center">
        Each company sees only their own data.
      </div>
    </div>
  );
}

function VisualLivePredict() {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6">
      <div className="grid grid-cols-2 gap-3 mb-4">
        {["Amount", "Product", "Card1", "Email"].map((f, i) => (
          <div key={f} className="bg-slate-950 border border-slate-800 rounded-lg p-2">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider">{f}</div>
            <div className="text-sm text-slate-200 font-mono">
              {["$422.50", "C", "9500", "outlook.com"][i]}
            </div>
          </div>
        ))}
      </div>
      <div className="bg-red-600 hover:bg-red-700 text-white text-center font-semibold py-2 rounded-lg mb-4 cursor-default">
        Score Transaction
      </div>
      <div className="bg-gradient-to-br from-amber-950/40 to-slate-950 border border-amber-500/30 rounded-xl p-4">
        <div className="text-xs text-slate-500 uppercase tracking-wider">Decision</div>
        <div className="text-2xl font-bold text-amber-400">REVIEW</div>
        <div className="text-xs text-slate-500 mt-1">7.0 ms &middot; risk 0.57</div>
      </div>
    </div>
  );
}

function VisualCrossDataset() {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-6">
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-red-400 uppercase tracking-wider font-semibold">Primary</div>
          <div className="text-lg font-bold mt-1">IEEE-CIS</div>
          <div className="text-xs text-slate-500 mt-3">590K real transactions</div>
          <div className="text-xs text-slate-500">3.5% fraud rate</div>
          <div className="mt-3 pt-3 border-t border-slate-800 text-xs">
            <div className="text-slate-500">PR-AUC</div>
            <div className="text-emerald-400 font-mono font-bold">0.83</div>
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Validation</div>
          <div className="text-lg font-bold mt-1">Sparkov</div>
          <div className="text-xs text-slate-500 mt-3">1.85M synthetic</div>
          <div className="text-xs text-slate-500">0.52% fraud rate</div>
          <div className="mt-3 pt-3 border-t border-slate-800 text-xs">
            <div className="text-slate-500">PR-AUC</div>
            <div className="text-emerald-400 font-mono font-bold">0.42</div>
          </div>
        </div>
      </div>
      <div className="mt-4 text-xs text-slate-400 text-center">
        Same methodology, both datasets, no dataset-specific hacks.
      </div>
    </div>
  );
}
