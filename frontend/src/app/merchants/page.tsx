"use client";

import Link from "next/link";
import { PublicShell } from "@/components/PublicShell";

type MerchantCard = {
  slug: string;
  href: string;
  displayName: string;
  tagline: string;
  logoLetter: string;
  primaryHex: string;
  primaryHexDark: string;
  category: string;
  sampleProducts: string;
  hint: string;
};

const MERCHANTS: MerchantCard[] = [
  {
    slug: "techmart",
    href: "/checkout",
    displayName: "TechMart Electronics",
    tagline: "Consumer electronics · online",
    logoLetter: "T",
    primaryHex: "#F43F5E",
    primaryHexDark: "#BE1F45",
    category: "shopping_net",
    sampleProducts: "Earbuds · Watch · TV · Laptop · Camera",
    hint: "USD-denominated demo storefront (default flow)",
  },
  {
    slug: "zomato",
    href: "/merchants/zomato",
    displayName: "Zomato",
    tagline: "Food delivery",
    logoLetter: "Z",
    primaryHex: "#E23744",
    primaryHexDark: "#B01E29",
    category: "misc_net",
    sampleProducts: "Biryani · Pizza · Wedding catering ₹2.5L",
    hint: "INR display, big-order bulk fraud trigger",
  },
  {
    slug: "swiggy",
    href: "/merchants/swiggy",
    displayName: "Swiggy",
    tagline: "Food + Instamart delivery",
    logoLetter: "S",
    primaryHex: "#FC8019",
    primaryHexDark: "#D66A0F",
    category: "misc_net",
    sampleProducts: "Meals · Corporate ₹55K · Conference catering ₹2.8L",
    hint: "INR display, corporate bulk order test cases",
  },
  {
    slug: "bigbasket",
    href: "/merchants/bigbasket",
    displayName: "BigBasket",
    tagline: "Online grocery",
    logoLetter: "B",
    primaryHex: "#84BE39",
    primaryHexDark: "#5F8B27",
    category: "grocery_pos",
    sampleProducts: "Veggies · Restaurant restock ₹1.4L · Wholesale ₹2.4L",
    hint: "grocery_pos category — strong Sparkov signal",
  },
];

export default function MerchantsShowcasePage() {
  return (
    <PublicShell>
      <div className="min-h-screen py-16 px-6">
        <div className="max-w-6xl mx-auto">
          {/* Hero */}
          <div className="text-center mb-14">
            <div className="inline-block px-3 py-1 rounded-full text-[10px] uppercase tracking-widest font-bold bg-red-500/10 text-red-400 border border-red-500/20 mb-4">
              Live demo showcase
            </div>
            <h1
              className="text-4xl sm:text-5xl font-black tracking-tight mb-4"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              Four merchant portals.<br />
              <span className="text-red-400">One fraud engine.</span>
            </h1>
            <p className="text-slate-400 max-w-2xl mx-auto text-sm sm:text-base leading-relaxed">
              Each portal below is independently branded — different colors,
              different product catalogs, different transaction categories.
              But every checkout call goes to the same <code className="text-red-400 font-mono">/api/checkout</code>{" "}
              endpoint, which routes transactions to the correct tenant via a{" "}
              <code className="text-red-400 font-mono">company_slug</code>.
              Click any card to try that merchant&rsquo;s checkout flow.
            </p>
          </div>

          {/* Merchant grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {MERCHANTS.map((m) => (
              <Link
                key={m.slug}
                href={m.href}
                className="group relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-6 transition hover:border-slate-600 hover:-translate-y-0.5"
              >
                {/* Accent stripe on left */}
                <div
                  className="absolute left-0 top-0 bottom-0 w-1.5 transition-all group-hover:w-2"
                  style={{
                    background: `linear-gradient(180deg, ${m.primaryHex} 0%, ${m.primaryHexDark} 100%)`,
                  }}
                />

                {/* Radial glow on hover */}
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-20 transition-opacity pointer-events-none"
                  style={{
                    background: `radial-gradient(circle at top right, ${m.primaryHex}, transparent 60%)`,
                  }}
                />

                <div className="relative flex items-start gap-4">
                  {/* Logo */}
                  <div
                    className="w-14 h-14 rounded-xl flex items-center justify-center font-black text-white text-xl shrink-0 shadow-lg"
                    style={{
                      background: `linear-gradient(135deg, ${m.primaryHex} 0%, ${m.primaryHexDark} 100%)`,
                      boxShadow: `0 8px 20px -8px ${m.primaryHex}80`,
                    }}
                  >
                    {m.logoLetter}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 flex-wrap">
                      <h2 className="text-xl font-bold text-white leading-tight">
                        {m.displayName}
                      </h2>
                      <span className="text-[10px] uppercase tracking-widest text-slate-500 font-semibold">
                        {m.tagline}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-slate-400 font-mono">
                      {m.sampleProducts}
                    </div>
                    <div className="mt-3 flex items-center gap-2 text-[11px]">
                      <span
                        className="px-2 py-0.5 rounded font-semibold uppercase tracking-wider"
                        style={{
                          background: `${m.primaryHex}15`,
                          color: m.primaryHex,
                        }}
                      >
                        category = {m.category}
                      </span>
                      <span className="text-slate-500">·</span>
                      <span className="text-slate-500 italic">{m.hint}</span>
                    </div>

                    {/* CTA */}
                    <div
                      className="mt-4 inline-flex items-center gap-1.5 text-sm font-bold group-hover:gap-3 transition-all"
                      style={{ color: m.primaryHex }}
                    >
                      Open checkout
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {/* How it works panel */}
          <div className="mt-10 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <h3 className="text-sm uppercase tracking-widest text-slate-400 font-bold mb-4">
              How the shared fraud API works
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <div className="text-red-400 font-bold text-lg mb-1">1.</div>
                <div className="text-slate-300 font-semibold mb-1">
                  Customer pays at merchant
                </div>
                <div className="text-slate-500 text-xs leading-relaxed">
                  User adds items, enters card details, clicks Pay. Merchant
                  frontend collects the payment payload.
                </div>
              </div>
              <div>
                <div className="text-red-400 font-bold text-lg mb-1">2.</div>
                <div className="text-slate-300 font-semibold mb-1">
                  Merchant portal POSTs to /api/checkout
                </div>
                <div className="text-slate-500 text-xs leading-relaxed">
                  Payload includes{" "}
                  <code className="text-red-400 font-mono">company_slug</code>{" "}
                  so the backend knows which tenant this transaction belongs
                  to. Backend enriches with velocity, geo, and customer
                  profile data.
                </div>
              </div>
              <div>
                <div className="text-red-400 font-bold text-lg mb-1">3.</div>
                <div className="text-slate-300 font-semibold mb-1">
                  Sparkov model scores → decision returned
                </div>
                <div className="text-slate-500 text-xs leading-relaxed">
                  LightGBM inference in ~80&nbsp;ms; transaction and
                  prediction persisted with the correct{" "}
                  <code className="text-red-400 font-mono">company_id</code>;
                  merchant gets an approve/decline/review verdict.
                </div>
              </div>
            </div>
          </div>

          {/* Analyst side */}
          <div className="mt-6 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900/60 to-red-950/20 p-6 flex flex-col sm:flex-row items-start sm:items-center gap-5">
            <div className="flex-1">
              <div className="text-[10px] uppercase tracking-widest text-red-400 font-bold mb-1">
                After the transaction
              </div>
              <div className="text-lg font-bold text-white mb-1">
                Each merchant admin sees only their own transactions
              </div>
              <div className="text-sm text-slate-400 leading-relaxed">
                Log in as{" "}
                <code className="text-red-400 font-mono">admin@zomato.demo</code>{" "}
                or{" "}
                <code className="text-red-400 font-mono">admin@swiggy.demo</code>{" "}
                to see the analyst dashboard filtered to that tenant. Every
                query filters on{" "}
                <code className="text-red-400 font-mono">company_id</code> —
                cross-tenant data access is impossible by construction.
              </div>
            </div>
            <Link
              href="/login"
              className="shrink-0 px-5 py-3 rounded-lg bg-gradient-to-br from-red-500 to-red-700 hover:from-red-600 hover:to-red-800 text-white font-semibold text-sm shadow-lg shadow-red-500/20 transition"
            >
              Open analyst login →
            </Link>
          </div>
        </div>
      </div>
    </PublicShell>
  );
}
