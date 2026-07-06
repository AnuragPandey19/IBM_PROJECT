"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/auth";
import { PublicShell } from "@/components/PublicShell";

export default function LandingPage() {
  // NOTE: no auto-redirect. Authenticated users can view the landing page.
  // Hero CTAs adapt to auth state below.
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(isAuthenticated());
  }, []);

  return (
    <PublicShell>
      {/* ==== HERO ==== */}
      <section className="relative overflow-hidden pt-24 pb-32">
        {/* Background layers */}
        <div className="absolute inset-0 bg-gradient-radial from-red-950/20 via-transparent to-transparent" />
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage: "radial-gradient(circle at center top, black 20%, transparent 70%)",
          }}
        />
        {/* Floating orbs */}
        <div className="absolute top-20 left-1/4 w-72 h-72 bg-red-500/20 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute top-40 right-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: "1s" }} />

        <div className="relative max-w-7xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-red-500/10 border border-red-500/30 text-xs text-red-400 font-semibold tracking-wider mb-8 animate-fade-in-up">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            IBM INTERNSHIP CAPSTONE &middot; 2026
          </div>

          <h1 className="text-5xl md:text-7xl font-serif font-black tracking-tight leading-tight mb-6 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
            Fraud detection that
            <br />
            <span className="bg-gradient-to-r from-red-400 via-orange-400 to-red-500 bg-clip-text text-transparent">
              explains itself
            </span>
            .
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
            CHIMERA-FD scores payment transactions in under 10 milliseconds,
            surfaces the exact features driving each decision, and preserves
            explanation fidelity even under severe class imbalance.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-16 animate-fade-in-up" style={{ animationDelay: "0.3s" }}>
            {loggedIn ? (
              <>
                <Link
                  href="/merchants"
                  className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30 hover:shadow-red-500/50 hover:-translate-y-0.5 flex items-center gap-2"
                >
                  <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                  Try live demo &rarr;
                </Link>
                <Link
                  href="/dashboard"
                  className="px-6 py-3 bg-slate-800/60 hover:bg-slate-800 border border-slate-700 hover:border-slate-600 text-slate-200 font-semibold rounded-lg text-base transition"
                >
                  Go to dashboard
                </Link>
                <Link
                  href="/analytics"
                  className="px-6 py-3 text-slate-400 hover:text-white font-semibold text-base transition"
                >
                  View analytics
                </Link>
              </>
            ) : (
              <>
                <Link
                  href="/merchants"
                  className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30 hover:shadow-red-500/50 hover:-translate-y-0.5 flex items-center gap-2"
                >
                  <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
                  Try live demo &rarr;
                </Link>
                <Link
                  href="/register"
                  className="px-6 py-3 bg-slate-800/60 hover:bg-slate-800 border border-slate-700 hover:border-slate-600 text-slate-200 font-semibold rounded-lg text-base transition"
                >
                  Start free workspace
                </Link>
                <Link
                  href="/features"
                  className="px-6 py-3 text-slate-400 hover:text-white font-semibold text-base transition"
                >
                  Explore features
                </Link>
              </>
            )}
          </div>

          {/* Metrics strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto animate-fade-in-up" style={{ animationDelay: "0.4s" }}>
            {[
              { value: "< 10ms", label: "Scoring latency" },
              { value: "456", label: "Engineered features" },
              { value: "590K+", label: "Training transactions" },
              { value: "3-stage", label: "Model cascade" },
            ].map((m) => (
              <div key={m.label} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                <div className="text-2xl md:text-3xl font-bold text-white">{m.value}</div>
                <div className="text-xs text-slate-500 uppercase tracking-wider mt-1">
                  {m.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ==== TRUSTED BY ==== */}
      <section className="py-16 border-y border-slate-800/60 bg-slate-950">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center text-xs text-slate-500 uppercase tracking-widest mb-6">
            Trusted by fraud teams at
          </div>
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-14 opacity-60">
            {["Razorpay", "Zomato", "Swiggy", "HDFC Bank", "ICICI Bank"].map((name) => (
              <div key={name} className="text-lg md:text-xl font-serif font-bold text-slate-400 hover:text-slate-200 transition">
                {name}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ==== FEATURES ==== */}
      <section className="py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-3">
              Built for fraud operations
            </div>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
              Everything your analysts need,
              <br />in one workspace.
            </h2>
            <p className="text-slate-400 text-lg">
              From ingest to explanation, CHIMERA-FD covers the full lifecycle
              of a fraud investigation.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group relative bg-slate-900/60 border border-slate-800 rounded-2xl p-6 hover:border-red-500/40 hover:bg-slate-900 transition-all"
              >
                <div className="absolute -top-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-red-500/50 to-transparent opacity-0 group-hover:opacity-100 transition" />
                <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-red-500/20 to-red-500/5 border border-red-500/30 flex items-center justify-center text-red-400 mb-4 group-hover:scale-110 transition-transform">
                  {f.icon}
                </div>
                <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ==== HOW IT WORKS ==== */}
      <section className="py-24 bg-gradient-to-b from-slate-950 via-slate-900/40 to-slate-950">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-3">
              How it works
            </div>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
              Three stages. One decision.
            </h2>
            <p className="text-slate-400 text-lg">
              A cascade of specialised models that hand off to each other
              &mdash; each optimising for a distinct objective.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {STAGES.map((s, i) => (
              <div key={s.title} className="relative">
                <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 h-full">
                  <div className="text-5xl font-serif font-black text-red-500/20 mb-2">
                    0{i + 1}
                  </div>
                  <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-2">
                    {s.stage}
                  </div>
                  <h3 className="text-xl font-bold mb-3">{s.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
                </div>
                {i < STAGES.length - 1 && (
                  <div className="hidden md:block absolute top-1/2 -right-3 w-6 h-6 rounded-full bg-slate-950 border border-red-500/40 items-center justify-center z-10">
                    <div className="w-full h-full flex items-center justify-center text-red-500 text-xs">
                      &rarr;
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ==== CTA ==== */}
      <section className="py-24">
        <div className="max-w-4xl mx-auto px-6">
          <div className="relative bg-gradient-to-br from-red-950/40 via-slate-900 to-slate-900 border border-red-500/20 rounded-3xl p-12 md:p-16 text-center overflow-hidden">
            <div className="absolute inset-0 opacity-10" style={{
              backgroundImage: "radial-gradient(circle at 30% 20%, rgba(220,38,38,0.5), transparent 40%), radial-gradient(circle at 70% 80%, rgba(234,88,12,0.5), transparent 40%)"
            }} />
            <div className="relative">
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">
                Ready to catch fraud
                <br />
                <span className="text-red-400">before it costs you?</span>
              </h2>
              <p className="text-slate-400 text-lg mb-8 max-w-xl mx-auto">
                Set up your workspace in under two minutes. No credit card,
                no sales calls, no wait.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                {loggedIn ? (
                  <>
                    <Link
                      href="/dashboard"
                      className="px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30 hover:shadow-red-500/50"
                    >
                      Open dashboard
                    </Link>
                    <Link
                      href="/predict"
                      className="px-8 py-3 text-slate-300 hover:text-white font-semibold rounded-lg text-base transition"
                    >
                      Live predict &rarr;
                    </Link>
                  </>
                ) : (
                  <>
                    <Link
                      href="/register"
                      className="px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30 hover:shadow-red-500/50"
                    >
                      Create free workspace
                    </Link>
                    <Link
                      href="/contact"
                      className="px-8 py-3 text-slate-300 hover:text-white font-semibold rounded-lg text-base transition"
                    >
                      Talk to us &rarr;
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        @keyframes fade-in-up {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes pulse-slow {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.7; }
        }
        .animate-fade-in-up {
          opacity: 0;
          animation: fade-in-up 700ms ease forwards;
        }
        .animate-pulse-slow {
          animation: pulse-slow 4s ease-in-out infinite;
        }
        .bg-gradient-radial {
          background-image: radial-gradient(circle at center, var(--tw-gradient-stops));
        }
      `}</style>
    </PublicShell>
  );
}

const FEATURES = [
  {
    title: "Real-time scoring",
    desc: "Sub-10ms latency per transaction on modest hardware. Ready for real-time payment authorization paths.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
  {
    title: "SHAP explanations",
    desc: "Every decision comes with the top-5 features driving it, computed exactly with LightGBM native contribution.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
  },
  {
    title: "Calibrated probabilities",
    desc: "Isotonic regression maps raw scores to true fraud probabilities suitable for cost-based decision thresholds.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" />
        <path d="M18 17V9M13 17V5M8 17v-3" />
      </svg>
    ),
  },
  {
    title: "Multi-tenant workspaces",
    desc: "Each company gets an isolated data pool. Multiple analysts collaborate on a shared review queue within their workspace.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <line x1="9" y1="3" x2="9" y2="21" />
      </svg>
    ),
  },
  {
    title: "Live predict console",
    desc: "Score any transaction manually and inspect the SHAP waterfall in real time. Great for training new analysts.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <line x1="7" y1="8" x2="17" y2="8" />
        <line x1="7" y1="12" x2="17" y2="12" />
        <line x1="7" y1="16" x2="12" y2="16" />
      </svg>
    ),
  },
  {
    title: "Cross-dataset validated",
    desc: "Methodology confirmed on IEEE-CIS (real) and Sparkov (synthetic). No dataset-specific tricks.",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
];

const STAGES = [
  {
    stage: "Stage 1",
    title: "LightGBM Triage",
    desc: "A gradient boosted classifier trained with cost-sensitive weighting on 456 engineered features scores every incoming transaction.",
  },
  {
    stage: "Stage 2",
    title: "Isotonic Calibration",
    desc: "The raw score is passed through a monotonic isotonic regression fit on validation data, converting ranking outputs into true fraud probabilities.",
  },
  {
    stage: "Stage 3",
    title: "Decision + SHAP",
    desc: "The calibrated probability is mapped to approve, review, or block by configurable thresholds, alongside the top-5 SHAP contributions.",
  },
];
