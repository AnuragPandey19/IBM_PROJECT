"use client";

import Link from "next/link";
import { PublicShell } from "@/components/PublicShell";

const TIERS = [
  {
    name: "Free",
    price: "₹0",
    period: "forever",
    tagline: "Perfect for evaluating the model and small teams.",
    features: [
      "Up to 3 analysts per workspace",
      "10,000 scored transactions per month",
      "SHAP explanations on every prediction",
      "5-minute uptime monitoring",
      "Community support",
    ],
    cta: "Get started",
    href: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: "₹9,999",
    period: "per month",
    tagline: "For growing fraud operations teams.",
    features: [
      "Up to 25 analysts per workspace",
      "500,000 scored transactions per month",
      "Priority scoring lane (sub-5ms P95)",
      "Prediction history retention: 12 months",
      "Alembic-managed schema migrations",
      "Email support with 24-hour SLA",
    ],
    cta: "Start Pro trial",
    href: "/register",
    highlight: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "annual contract",
    tagline: "For banks and payment processors at scale.",
    features: [
      "Unlimited analysts",
      "Unlimited scored transactions",
      "Dedicated inference cluster",
      "SSO via SAML / OIDC",
      "Custom model retraining pipeline",
      "White-glove onboarding",
      "24/7 phone support with 15-minute SLA",
    ],
    cta: "Contact sales",
    href: "/contact",
    highlight: false,
  },
];

const FAQS = [
  {
    q: "Is my transaction data isolated from other companies?",
    a: "Yes. Every transaction, prediction, and user is scoped to a company at the database level. Cross-tenant visibility is zero by construction; every query enforces the company filter before returning results.",
  },
  {
    q: "Can I upgrade or downgrade at any time?",
    a: "Yes. Plan changes take effect at the start of the next billing cycle. Downgrades preserve all your existing data; if you exceed the new plan's transaction limits, we apply overage rates rather than dropping data.",
  },
  {
    q: "Do you offer academic or non-profit discounts?",
    a: "Yes. Verified academic institutions and non-profit organizations receive a 50% discount on Pro and Enterprise plans. Contact us with your institutional email for verification.",
  },
  {
    q: "What happens to my data if I cancel?",
    a: "You can export all your data (transactions, predictions, analyst logs) as JSON at any time. Ninety days after cancellation, all customer data is permanently deleted from our systems.",
  },
  {
    q: "How does the free tier stay free?",
    a: "CHIMERA-FD started as an academic capstone project. The free tier is subsidised by paying Pro and Enterprise customers as part of our commitment to making explainable fraud detection accessible to independent researchers and small teams.",
  },
  {
    q: "Do you support on-premise deployment?",
    a: "Enterprise plans include the option of a self-hosted deployment inside your VPC. We provide the Docker images, Helm charts, and operational documentation. You retain full control of your data and model artifacts.",
  },
];

export default function PricingPage() {
  return (
    <PublicShell>
      {/* Hero */}
      <section className="pt-24 pb-8 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-radial from-red-950/20 via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <div className="text-xs text-red-400 uppercase tracking-widest font-semibold mb-4">
            Pricing
          </div>
          <h1 className="text-4xl md:text-6xl font-serif font-black tracking-tight mb-6">
            Simple, transparent pricing.
          </h1>
          <p className="text-lg text-slate-400 leading-relaxed">
            Start free, upgrade when you outgrow it. No sales calls,
            no hidden fees, no surprises.
          </p>
        </div>
      </section>

      {/* Tiers */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={`relative bg-slate-900/60 border rounded-3xl p-8 flex flex-col ${
                t.highlight
                  ? "border-red-500/50 shadow-2xl shadow-red-500/10 scale-[1.02]"
                  : "border-slate-800"
              }`}
            >
              {t.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-red-600 text-white text-[10px] font-bold tracking-widest px-3 py-1 rounded-full">
                  MOST POPULAR
                </div>
              )}
              <div className="text-lg font-bold text-slate-200 mb-1">{t.name}</div>
              <div className="flex items-baseline gap-2 mb-2">
                <span className="text-4xl font-black tracking-tight">{t.price}</span>
                <span className="text-sm text-slate-500">/ {t.period}</span>
              </div>
              <p className="text-sm text-slate-400 mb-6">{t.tagline}</p>

              <ul className="space-y-3 mb-8 flex-1">
                {t.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                    <span className="w-4 h-4 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center text-red-400 text-[10px] shrink-0 mt-0.5">
                      &#10003;
                    </span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={t.href}
                className={`text-center font-semibold py-3 rounded-lg transition ${
                  t.highlight
                    ? "bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/20"
                    : "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
                }`}
              >
                {t.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Feature comparison */}
      <section className="py-16">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-3">
            Compare plans
          </h2>
          <p className="text-slate-400 text-center mb-10">Everything you get on each tier, at a glance.</p>

          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-950 text-xs text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left px-6 py-3">Feature</th>
                  <th className="text-center px-4 py-3">Free</th>
                  <th className="text-center px-4 py-3 text-red-400">Pro</th>
                  <th className="text-center px-4 py-3">Enterprise</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {COMPARISON.map((row) => (
                  <tr key={row.name}>
                    <td className="px-6 py-3 text-slate-300">{row.name}</td>
                    <td className="text-center px-4 py-3 text-slate-400">{row.free}</td>
                    <td className="text-center px-4 py-3 text-slate-200 font-semibold">{row.pro}</td>
                    <td className="text-center px-4 py-3 text-slate-400">{row.enterprise}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16">
        <div className="max-w-3xl mx-auto px-6">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-10">
            Frequently asked questions
          </h2>
          <div className="space-y-3">
            {FAQS.map((f) => (
              <details
                key={f.q}
                className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition group"
              >
                <summary className="cursor-pointer text-base font-semibold list-none flex justify-between items-center">
                  <span>{f.q}</span>
                  <span className="text-red-400 group-open:rotate-45 transition-transform">+</span>
                </summary>
                <p className="text-sm text-slate-400 mt-3 leading-relaxed">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Still deciding?
          </h2>
          <p className="text-slate-400 text-lg mb-8">
            Start on the free tier. Upgrade only when you outgrow it.
          </p>
          <Link
            href="/register"
            className="inline-block px-8 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg text-base transition shadow-xl shadow-red-500/30"
          >
            Create free workspace &rarr;
          </Link>
        </div>
      </section>
    </PublicShell>
  );
}

const COMPARISON = [
  { name: "Analysts per workspace", free: "3", pro: "25", enterprise: "Unlimited" },
  { name: "Scored transactions / month", free: "10K", pro: "500K", enterprise: "Unlimited" },
  { name: "SHAP explanations", free: "✓", pro: "✓", enterprise: "✓" },
  { name: "Calibrated probabilities", free: "✓", pro: "✓", enterprise: "✓" },
  { name: "Data retention", free: "30 days", pro: "12 months", enterprise: "Custom" },
  { name: "Priority scoring lane", free: "—", pro: "✓", enterprise: "✓" },
  { name: "SSO (SAML / OIDC)", free: "—", pro: "—", enterprise: "✓" },
  { name: "Self-hosted deployment", free: "—", pro: "—", enterprise: "✓" },
  { name: "Custom model retraining", free: "—", pro: "—", enterprise: "✓" },
  { name: "Support SLA", free: "Community", pro: "24-hour email", enterprise: "15-min phone" },
];
