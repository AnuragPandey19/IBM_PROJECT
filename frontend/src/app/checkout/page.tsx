"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

type Product = {
  id: string;
  name: string;
  price: number;
  image: string;
};

type CustomerProfile = {
  key: string;
  label: string;
  description: string;
  card_last4: string;
  home_city: string;
  avg_past_amt: number;
  prior_transaction_count: number;
};

type ProfilesResponse = {
  profiles: CustomerProfile[];
  demo_merchant: string;
  demo_products: Product[];
};

type CheckoutResponse = {
  status: string;
  transaction_id: string;
  authorization_code: string | null;
  amount_charged: number;
  merchant_name: string;
  card_last4: string;
  decision_reason: string;
  risk_score: number;
  decision_time_ms: number;
  created_at: string;
  internal_prediction_id: number;
  internal_shap_top: { feature: string; value: unknown; contribution: number }[];
};

type CartItem = { product: Product; qty: number };

const fmtMoney = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

const HOUR_OPTIONS = [
  { value: "", label: "Current time (server)" },
  { value: "3", label: "3 AM (night)" },
  { value: "9", label: "9 AM (morning)" },
  { value: "14", label: "2 PM (afternoon)" },
  { value: "21", label: "9 PM (evening)" },
];

const CATEGORY_OPTIONS = [
  { value: "shopping_net", label: "Online shopping (default)" },
  { value: "grocery_pos", label: "Grocery in-store" },
  { value: "gas_transport", label: "Gas / Transport" },
  { value: "misc_net", label: "Misc online" },
  { value: "entertainment", label: "Entertainment" },
];

export default function CheckoutPage() {
  const [profiles, setProfiles] = useState<CustomerProfile[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [merchantName, setMerchantName] = useState<string>("TechMart Electronics");
  const [cart, setCart] = useState<CartItem[]>([]);

  // Payment form
  const [cardholderName, setCardholderName] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("12/29");
  const [cvv, setCvv] = useState("123");
  const [email, setEmail] = useState("");

  // Demo controls
  const [selectedProfile, setSelectedProfile] = useState<string>("established");
  const [demoHour, setDemoHour] = useState<string>("");
  const [category, setCategory] = useState<string>("shopping_net");

  // Result state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CheckoutResponse | null>(null);
  const [showDeveloperView, setShowDeveloperView] = useState(false);

  const loadProfiles = useCallback(async () => {
    try {
      const data = await api<ProfilesResponse>("/api/checkout/profiles", { auth: false });
      setProfiles(data.profiles);
      setProducts(data.demo_products);
      setMerchantName(data.demo_merchant);
      if (data.demo_products.length > 0) {
        setCart([{ product: data.demo_products[0], qty: 1 }]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load checkout data");
    }
  }, []);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  // Auto-fill payment form when profile changes
  useEffect(() => {
    const p = profiles.find((x) => x.key === selectedProfile);
    if (p) {
      setCardNumber(`4532 1111 2222 ${p.card_last4}`);
      // cardholder + email default only if user hasn't touched
      if (!cardholderName) setCardholderName(labelToName(p.label));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, profiles]);

  const cartTotal = cart.reduce((sum, item) => sum + item.product.price * item.qty, 0);

  function addToCart(product: Product) {
    setCart((c) => {
      const existing = c.find((i) => i.product.id === product.id);
      if (existing) {
        return c.map((i) => (i.product.id === product.id ? { ...i, qty: i.qty + 1 } : i));
      }
      return [...c, { product, qty: 1 }];
    });
  }

  function updateQty(productId: string, qty: number) {
    if (qty <= 0) {
      setCart((c) => c.filter((i) => i.product.id !== productId));
    } else {
      setCart((c) => c.map((i) => (i.product.id === productId ? { ...i, qty } : i)));
    }
  }

  async function handlePay() {
    if (cartTotal <= 0) {
      setError("Add at least one item to your cart.");
      return;
    }
    if (!cardholderName.trim()) {
      setError("Cardholder name is required.");
      return;
    }
    setError(null);
    setLoading(true);
    setResult(null);

    const body = {
      card_number: cardNumber.replace(/\s+/g, ""),
      cardholder_name: cardholderName,
      card_expiry: expiry,
      card_cvv: cvv,
      amount: cartTotal,
      merchant_name: merchantName,
      merchant_category: category,
      cust_email: email || undefined,
      company_slug: "techmart",   // Routes txn to TechMart Electronics company_id
      demo_profile: selectedProfile,
      demo_hour_override: demoHour ? parseInt(demoHour, 10) : undefined,
    };

    try {
      const data = await api<CheckoutResponse>("/api/checkout", {
        method: "POST",
        body,
        auth: false,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Checkout failed");
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setError(null);
    setShowDeveloperView(false);
  }

  // ---- Result screen (approved / declined / review) ----
  if (result) {
    return (
      <ResultScreen
        result={result}
        showDeveloperView={showDeveloperView}
        onToggleDev={() => setShowDeveloperView(!showDeveloperView)}
        onReset={reset}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header — mock e-commerce header */}
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center font-bold text-white">
              T
            </div>
            <div>
              <div className="font-bold text-lg leading-tight">{merchantName}</div>
              <div className="text-[10px] text-slate-500 tracking-widest uppercase">Secure checkout</div>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span className="hidden sm:flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              256-bit SSL
            </span>
            <span className="hidden sm:inline">·</span>
            <span className="hidden sm:flex items-center gap-1.5 text-red-400 font-semibold">
              Powered by CHIMERA-FD
            </span>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* LEFT — Products + cart */}
        <div className="lg:col-span-3 space-y-6">
          <section>
            <h2 className="text-sm uppercase tracking-widest font-bold text-slate-400 mb-3">
              Available items
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {products.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => addToCart(p)}
                  className="bg-slate-900/60 border border-slate-800 hover:border-red-500/40 rounded-xl p-3 text-left transition group"
                >
                  <div className="text-4xl mb-2">{p.image}</div>
                  <div className="text-xs font-semibold text-slate-200 leading-tight line-clamp-2">
                    {p.name}
                  </div>
                  <div className="text-sm font-mono font-bold text-red-400 mt-1">
                    {fmtMoney(p.price)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-1 group-hover:text-red-400 transition">
                    + Add to cart
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-sm uppercase tracking-widest font-bold text-slate-400 mb-3">
              Your cart
            </h2>
            {cart.length === 0 ? (
              <div className="border border-dashed border-slate-800 rounded-xl p-8 text-center text-sm text-slate-500">
                Your cart is empty. Add an item above to continue.
              </div>
            ) : (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
                {cart.map((item) => (
                  <div
                    key={item.product.id}
                    className="flex items-center gap-3 p-3 border-b border-slate-800 last:border-b-0"
                  >
                    <div className="text-2xl">{item.product.image}</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold truncate">{item.product.name}</div>
                      <div className="text-xs text-slate-500 font-mono">
                        {fmtMoney(item.product.price)} each
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => updateQty(item.product.id, item.qty - 1)}
                        className="w-7 h-7 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-lg leading-none"
                      >
                        −
                      </button>
                      <span className="w-6 text-center text-sm font-mono">{item.qty}</span>
                      <button
                        type="button"
                        onClick={() => updateQty(item.product.id, item.qty + 1)}
                        className="w-7 h-7 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-lg leading-none"
                      >
                        +
                      </button>
                    </div>
                    <div className="text-sm font-mono font-bold w-20 text-right">
                      {fmtMoney(item.product.price * item.qty)}
                    </div>
                  </div>
                ))}
                <div className="p-3 flex items-center justify-between bg-slate-950/50">
                  <span className="text-sm font-semibold text-slate-300">Order total</span>
                  <span className="text-xl font-mono font-black text-red-400">
                    {fmtMoney(cartTotal)}
                  </span>
                </div>
              </div>
            )}
          </section>
        </div>

        {/* RIGHT — Payment form */}
        <div className="lg:col-span-2">
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 sticky top-6">
            <h2 className="text-sm uppercase tracking-widest font-bold text-slate-400 mb-4">
              Payment details
            </h2>

            <div className="space-y-3">
              <FormField label="Cardholder name">
                <input
                  type="text"
                  value={cardholderName}
                  onChange={(e) => setCardholderName(e.target.value)}
                  placeholder="John Smith"
                  className={inputCls}
                />
              </FormField>
              <FormField label="Card number">
                <input
                  type="text"
                  value={cardNumber}
                  onChange={(e) => setCardNumber(e.target.value)}
                  placeholder="4532 1111 2222 1234"
                  className={inputCls + " font-mono"}
                />
              </FormField>
              <div className="grid grid-cols-2 gap-3">
                <FormField label="Expiry">
                  <input
                    type="text"
                    value={expiry}
                    onChange={(e) => setExpiry(e.target.value)}
                    placeholder="MM/YY"
                    className={inputCls + " font-mono"}
                  />
                </FormField>
                <FormField label="CVV">
                  <input
                    type="text"
                    value={cvv}
                    onChange={(e) => setCvv(e.target.value)}
                    placeholder="123"
                    className={inputCls + " font-mono"}
                  />
                </FormField>
              </div>
              <FormField label="Email (optional)">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className={inputCls}
                />
              </FormField>
            </div>

            {/* Demo controls — a real gateway would not surface these */}
            <div className="mt-5 pt-4 border-t border-dashed border-slate-800">
              <div className="text-[10px] uppercase tracking-widest font-bold text-amber-400 mb-2 flex items-center gap-1.5">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 9v4m0 4h.01" />
                  <circle cx="12" cy="12" r="10" />
                </svg>
                Demo controls (not in real gateways)
              </div>
              <div className="space-y-3">
                <FormField label="Customer profile">
                  <select
                    value={selectedProfile}
                    onChange={(e) => setSelectedProfile(e.target.value)}
                    className={inputCls}
                  >
                    {profiles.map((p) => (
                      <option key={p.key} value={p.key}>
                        {p.label} · avg ${p.avg_past_amt.toFixed(0)} · {p.prior_transaction_count} prior
                      </option>
                    ))}
                  </select>
                </FormField>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Force hour">
                    <select
                      value={demoHour}
                      onChange={(e) => setDemoHour(e.target.value)}
                      className={inputCls}
                    >
                      {HOUR_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </FormField>
                  <FormField label="Category">
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className={inputCls}
                    >
                      {CATEGORY_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </FormField>
                </div>
              </div>
            </div>

            {error && (
              <div className="mt-4 text-xs text-red-400 border border-red-500/30 bg-red-500/10 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="button"
              onClick={handlePay}
              disabled={loading || cartTotal <= 0}
              className="mt-5 w-full py-3 rounded-lg bg-gradient-to-br from-red-500 to-red-700 hover:from-red-600 hover:to-red-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm shadow-lg shadow-red-500/20 transition"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                  Authorizing payment&hellip;
                </span>
              ) : (
                <span>Pay {fmtMoney(cartTotal)}</span>
              )}
            </button>

            <div className="mt-3 text-[10px] text-slate-500 text-center">
              Your payment is scored by CHIMERA-FD&apos;s LightGBM model in real-time.
              <br />
              No money is actually charged.
            </div>
          </div>
        </div>
      </div>

      <footer className="border-t border-slate-800 mt-12">
        <div className="max-w-6xl mx-auto px-6 py-6 text-xs text-slate-500 flex flex-wrap items-center justify-between gap-3">
          <span>Demo storefront powered by CHIMERA-FD fraud detection API</span>
          <Link href="/" className="text-slate-400 hover:text-red-400 transition">
            ← Back to CHIMERA-FD
          </Link>
        </div>
      </footer>
    </div>
  );
}

// ------------------------------------------------------------------
// Result screen — shown after /api/checkout returns
// ------------------------------------------------------------------

function ResultScreen({
  result, showDeveloperView, onToggleDev, onReset,
}: {
  result: CheckoutResponse;
  showDeveloperView: boolean;
  onToggleDev: () => void;
  onReset: () => void;
}) {
  const isApproved = result.status === "approved";
  const isDeclined = result.status === "declined";
  const isReview = result.status === "review";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-start justify-center pt-16 pb-16 px-6">
      <div className="w-full max-w-lg">
        {/* Big status badge */}
        <div className={`rounded-2xl border p-8 text-center ${
          isApproved
            ? "bg-emerald-500/10 border-emerald-500/30"
            : isDeclined
            ? "bg-red-500/10 border-red-500/30"
            : "bg-amber-500/10 border-amber-500/30"
        }`}>
          <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center mb-4 ${
            isApproved ? "bg-emerald-500/20" : isDeclined ? "bg-red-500/20" : "bg-amber-500/20"
          }`}>
            {isApproved ? (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-emerald-400">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : isDeclined ? (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-red-400">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-amber-400">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            )}
          </div>
          <div className={`text-3xl font-black tracking-tight ${
            isApproved ? "text-emerald-300" : isDeclined ? "text-red-300" : "text-amber-300"
          }`} style={{ fontFamily: "var(--font-serif)" }}>
            {isApproved ? "Payment Approved" : isDeclined ? "Payment Declined" : "Verification Required"}
          </div>
          <div className="text-sm text-slate-400 mt-2 leading-relaxed">
            {result.decision_reason}
          </div>
        </div>

        {/* Receipt-style details */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 mt-4 space-y-2 text-sm">
          <ReceiptRow label="Merchant" value={result.merchant_name} />
          <ReceiptRow label="Amount" value={
            new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(result.amount_charged)
          } bold />
          <ReceiptRow label="Card" value={`•••• •••• •••• ${result.card_last4}`} mono />
          <ReceiptRow label="Transaction ID" value={result.transaction_id} mono small />
          {result.authorization_code && (
            <ReceiptRow label="Authorization" value={result.authorization_code} mono small />
          )}
          <ReceiptRow
            label="Processed in"
            value={`${result.decision_time_ms.toFixed(1)} ms`}
            small
          />
        </div>

        {/* Developer view toggle */}
        <div className="mt-4 flex items-center justify-between text-xs">
          <button
            type="button"
            onClick={onToggleDev}
            className="text-slate-500 hover:text-slate-300 underline"
          >
            {showDeveloperView ? "Hide" : "Show"} developer view (internal risk data)
          </button>
          <button
            type="button"
            onClick={onReset}
            className="text-slate-300 hover:text-red-400 font-semibold"
          >
            Try another →
          </button>
        </div>

        {/* Developer view */}
        {showDeveloperView && (
          <div className="mt-4 bg-slate-900/60 border border-slate-800 rounded-2xl p-5 font-mono text-xs">
            <div className="text-slate-400 mb-3 uppercase tracking-widest text-[10px] font-bold">
              Internal fraud engine payload
            </div>
            <div className="space-y-1 text-slate-300">
              <div><span className="text-slate-500">status:</span> {result.status}</div>
              <div><span className="text-slate-500">calibrated_risk_score:</span> {result.risk_score.toFixed(6)}</div>
              <div><span className="text-slate-500">model_decision:</span> {result.status === "approved" ? "approve" : result.status === "declined" ? "block" : "review"}</div>
              <div><span className="text-slate-500">prediction_id:</span> #{result.internal_prediction_id}</div>
            </div>
            <div className="mt-3 text-slate-500 uppercase tracking-widest text-[10px] font-bold">SHAP top-5</div>
            <div className="mt-2 space-y-1">
              {result.internal_shap_top.map((s, i) => {
                const contrib = s.contribution;
                const isFraud = contrib > 0;
                return (
                  <div key={i} className="flex items-center gap-2 text-[11px]">
                    <span className="text-slate-400 w-40 truncate">{s.feature}</span>
                    <span className="text-slate-600">=</span>
                    <span className="text-slate-300 w-24 truncate">{String(s.value)}</span>
                    <span className={`ml-auto font-bold ${isFraud ? "text-red-400" : "text-emerald-400"}`}>
                      {contrib > 0 ? "+" : ""}{contrib.toFixed(3)}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] text-slate-400">
              Analyst dashboard: <Link href="/login" className="text-red-400 hover:underline">log in as SecureBuy Electronics admin</Link> to see this transaction in the flagged queue.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------
// Local helpers
// ------------------------------------------------------------------

const inputCls =
  "w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-red-500";

function FormField({
  label, children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">
        {label}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function ReceiptRow({
  label, value, mono, bold, small,
}: {
  label: string;
  value: string;
  mono?: boolean;
  bold?: boolean;
  small?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500 text-xs uppercase tracking-wider">{label}</span>
      <span
        className={`${mono ? "font-mono" : ""} ${bold ? "font-bold text-white text-base" : "text-slate-200"} ${
          small ? "text-xs" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function labelToName(label: string): string {
  const map: Record<string, string> = {
    "Established Regular": "John Smith",
    "New Customer": "Sarah Johnson",
    "High-Value Regular": "Michael Chen",
    "Senior Cardholder": "Margaret Williams",
  };
  return map[label] ?? "";
}
