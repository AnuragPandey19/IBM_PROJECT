"use client";

import Link from "next/link";
import { PublicShell } from "@/components/PublicShell";

const TEAM = [
  {
    name: "Anurag Pandey",
    role: "System Architecture & Full-Stack",
    bio: "Backend API design (FastAPI, PostgreSQL, JWT), frontend development (Next.js dashboard, SHAP waterfall), and cloud deployment (Docker, Hugging Face Spaces, Render).",
    initials: "AP",
  },
  {
    name: "Pankaj Singh",
    role: "Model Engineering",
    bio: "Model research and comparative testing across gradient boosting families, IEEE-CIS dataset preparation, feature engineering pipeline, and Stage 1 hyperparameter tuning.",
    initials: "PS",
  },
  {
    name: "Gurnoor Multani",
    role: "Research & Methodology",
    bio: "Literature review, identification of the explainability-imbalance research gap, and design of the cost-sensitive cascaded methodology addressed by this work.",
    initials: "GM",
  },
  {
    name: "Sanvi Bharadwaj",
    role: "Cross-Dataset Validation",
    bio: "Sparkov dataset acquisition and Sparkov-specific feature engineering. Application of the shared methodology to confirm generalization across data distributions.",
    initials: "SB",
  },
];

export default function AboutPage() {
  return (
    <PublicShell>
      {/* Hero */}
      <section className="pt-24 pb-16 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-radial from-red-950/20 via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-4">
            About CHIMERA-FD
          </div>
          <h1 className="text-4xl md:text-6xl font-serif font-black tracking-tight mb-6">
            Fraud detection built by
            <br />
            <span className="text-red-400">researchers, for operators.</span>
          </h1>
          <p className="text-lg text-slate-400 leading-relaxed">
            Four undergraduate researchers on a mission to close the explainability-imbalance
            gap that has quietly plagued production fraud systems for over a decade.
          </p>
        </div>
      </section>

      {/* Mission */}
      <section className="py-16">
        <div className="max-w-4xl mx-auto px-6">
          <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-8 md:p-12">
            <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-3">
              Our mission
            </div>
            <h2 className="text-3xl md:text-4xl font-bold mb-6 leading-tight">
              Every automated fraud decision should be explainable, faithful, and fast.
            </h2>
            <div className="text-slate-300 space-y-4 leading-relaxed">
              <p>
                In 2026, financial institutions still make millions of automated
                fraud decisions each day using opaque black-box models. When a
                customer is wrongly declined, the analyst reviewing the flag can
                rarely explain <em>why</em> beyond &quot;the model said so.&quot;
                Regulators are asking harder questions, and the industry does not
                have a coherent answer.
              </p>
              <p>
                A recent paper by Zafar and Wu (AI Review, 2026) exposed a subtle
                but critical flaw: the synthetic oversampling techniques used to
                handle class imbalance in fraud detection corrupt the SHAP
                explanations that regulators and analysts depend on. This is the
                <span className="text-red-400 font-semibold"> explainability-imbalance paradox</span>.
              </p>
              <p>
                CHIMERA-FD is our proof that you don&apos;t have to choose. By
                using cost-sensitive learning instead of synthetic augmentation, a
                three-stage cascade of specialised models, and a calibration layer
                that preserves probability semantics, we deliver detection quality
                that is competitive with published baselines while keeping every
                explanation faithful to the real data distribution.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-3">
              The team
            </div>
            <h2 className="text-3xl md:text-4xl font-bold">Four collaborators, one goal.</h2>
            <p className="text-slate-400 mt-3 max-w-2xl mx-auto">
              No leaders, no hierarchy. Every decision reached by consensus,
              recorded in a shared project journal.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {TEAM.map((m) => (
              <div
                key={m.name}
                className="group bg-slate-900/60 border border-slate-800 rounded-2xl p-6 hover:border-red-500/40 hover:bg-slate-900 transition-all"
              >
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-lg shadow-red-500/20 group-hover:scale-105 transition">
                    {m.initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-lg font-bold">{m.name}</div>
                    <div className="text-xs text-red-400 uppercase tracking-wider font-semibold mb-2">
                      {m.role}
                    </div>
                    <p className="text-sm text-slate-400 leading-relaxed">{m.bio}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Tech stack */}
      <section className="py-16">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-3">
              Built with
            </div>
            <h2 className="text-3xl md:text-4xl font-bold">
              Modern, boring technology.
            </h2>
            <p className="text-slate-400 mt-3">
              We chose reliable, well-documented tools over trendy ones.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { name: "Python 3.11", type: "Language" },
              { name: "FastAPI", type: "Backend" },
              { name: "PostgreSQL", type: "Database" },
              { name: "SQLAlchemy 2.0", type: "ORM" },
              { name: "Next.js 15", type: "Frontend" },
              { name: "TypeScript", type: "Type safety" },
              { name: "Tailwind CSS", type: "Styling" },
              { name: "LightGBM 4.3", type: "Stage 1 model" },
              { name: "Isotonic Regression", type: "Stage 3 calibrator" },
              { name: "PyTorch Geometric", type: "GraphSAGE" },
              { name: "SHAP", type: "Explainability" },
              { name: "Docker", type: "Deployment" },
            ].map((t) => (
              <div key={t.name} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 hover:border-red-500/30 transition">
                <div className="text-base font-semibold">{t.name}</div>
                <div className="text-xs text-slate-500 mt-0.5">{t.type}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Want to try it yourself?
          </h2>
          <p className="text-slate-400 text-lg mb-8">
            Set up a free workspace and score your first transaction in
            under two minutes.
          </p>
          <Link
            href="/register"
            className="inline-block px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30"
          >
            Get started &rarr;
          </Link>
        </div>
      </section>
    </PublicShell>
  );
}
