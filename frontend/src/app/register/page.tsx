"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";

type RegisterResponse = {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  company: { id: number; name: string } | null;
};

const INDUSTRIES = [
  "Payment Gateway",
  "Banking",
  "E-commerce",
  "Fintech",
  "Insurance",
  "Cryptocurrency",
  "Other",
];

const COMPANY_SIZES = [
  "Startup (1-50)",
  "SMB (51-500)",
  "Mid-market (501-5000)",
  "Enterprise (5000+)",
];

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);

  // Step 1 — Company details
  const [companyName, setCompanyName] = useState("");
  const [industry, setIndustry] = useState(INDUSTRIES[0]);
  const [size, setSize] = useState(COMPANY_SIZES[0]);
  const [useCase, setUseCase] = useState("");

  // Step 2 — Admin details
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  function validateStep1(): string | null {
    if (!companyName.trim() || companyName.trim().length < 2) {
      return "Company name must be at least 2 characters";
    }
    return null;
  }

  function validateStep2(): string | null {
    if (!email.trim()) return "Email is required";
    if (!password) return "Password is required";
    if (password.length < 8) return "Password must be at least 8 characters";
    if (password !== confirmPassword) return "Passwords do not match";
    return null;
  }

  function goToStep2(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const err = validateStep1();
    if (err) {
      setError(err);
      return;
    }
    setStep(2);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const err = validateStep2();
    if (err) {
      setError(err);
      return;
    }

    setLoading(true);
    try {
      await api<RegisterResponse>("/auth/register", {
        method: "POST",
        body: {
          email: email.trim(),
          password,
          full_name: fullName.trim() || null,
          company_name: companyName.trim(),
          industry,
          size,
          use_case: useCase.trim() || null,
        },
        auth: false,
      });
      setSuccess(true);
      setTimeout(() => router.push("/login"), 1800);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError(err.message || "Email or company name already registered.");
        } else if (err.status === 422) {
          setError("Invalid input. Check email format and password length (min 8).");
        } else {
          setError(err.message);
        }
      } else {
        setError("Could not reach the server. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4">
        <div className="w-full max-w-md text-center">
          <div className="text-emerald-400 text-6xl mb-4">&#10003;</div>
          <h1 className="text-2xl font-bold text-white mb-2">Workspace created</h1>
          <p className="text-slate-400 mb-2">
            <span className="text-red-400 font-semibold">{companyName}</span> is now set up.
          </p>
          <p className="text-slate-400">Redirecting to sign in&hellip;</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4 py-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="text-xs tracking-widest text-red-500 font-bold mb-2">
            IBM INTERNSHIP &middot; 2026
          </div>
          <h1 className="text-4xl font-serif font-bold text-white mb-2">
            CHIMERA-FD
          </h1>
          <p className="text-slate-400 text-sm">
            Financial Transaction Fraud Detection
          </p>
        </div>

        {/* Progress indicator */}
        <div className="flex items-center justify-center mb-6 gap-3">
          <div className={`flex items-center gap-2 ${step === 1 ? "text-red-400" : "text-emerald-400"}`}>
            <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
              step === 1 ? "border-red-400 bg-red-500/20" : "border-emerald-400 bg-emerald-500/20"
            }`}>
              {step > 1 ? "✓" : "1"}
            </div>
            <span className="text-sm font-medium">Company</span>
          </div>
          <div className={`w-8 h-0.5 ${step > 1 ? "bg-emerald-400" : "bg-slate-700"}`} />
          <div className={`flex items-center gap-2 ${step === 2 ? "text-red-400" : "text-slate-500"}`}>
            <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
              step === 2 ? "border-red-400 bg-red-500/20" : "border-slate-700"
            }`}>
              2
            </div>
            <span className="text-sm font-medium">Admin</span>
          </div>
        </div>

        {step === 1 && (
          <form
            onSubmit={goToStep2}
            className="bg-slate-800/60 backdrop-blur border border-slate-700 rounded-2xl p-8 shadow-2xl"
          >
            <h2 className="text-xl font-semibold text-white mb-1">
              Step 1 &mdash; Tell us about your company
            </h2>
            <p className="text-xs text-slate-400 mb-6">
              You&apos;ll be the admin of this workspace.
            </p>

            <label className="block mb-4">
              <span className="text-sm text-slate-300 mb-1 block">Company name</span>
              <input
                type="text"
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Razorpay, HDFC Bank, Zomato"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition"
              />
            </label>

            <label className="block mb-4">
              <span className="text-sm text-slate-300 mb-1 block">Industry</span>
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500"
              >
                {INDUSTRIES.map((i) => (
                  <option key={i} value={i}>{i}</option>
                ))}
              </select>
            </label>

            <label className="block mb-4">
              <span className="text-sm text-slate-300 mb-1 block">Company size</span>
              <select
                value={size}
                onChange={(e) => setSize(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-red-500"
              >
                {COMPANY_SIZES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </label>

            <label className="block mb-6">
              <span className="text-sm text-slate-300 mb-1 block">Primary use case (optional)</span>
              <textarea
                value={useCase}
                onChange={(e) => setUseCase(e.target.value)}
                placeholder="e.g. Card-not-present fraud screening for online orders"
                rows={2}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition resize-none"
              />
            </label>

            {error && (
              <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-2.5 rounded-lg transition"
            >
              Continue &rarr;
            </button>

            <div className="text-center text-sm text-slate-400 mt-6">
              Already have an account?{" "}
              <Link href="/login" className="text-red-400 hover:text-red-300 font-medium">
                Sign in
              </Link>
            </div>
          </form>
        )}

        {step === 2 && (
          <form
            onSubmit={handleSubmit}
            className="bg-slate-800/60 backdrop-blur border border-slate-700 rounded-2xl p-8 shadow-2xl"
          >
            <h2 className="text-xl font-semibold text-white mb-1">
              Step 2 &mdash; Your admin account
            </h2>
            <p className="text-xs text-slate-400 mb-6">
              You&apos;ll be the admin of{" "}
              <span className="text-slate-200 font-semibold">{companyName}</span>.
            </p>

            <label className="block mb-4">
              <span className="text-sm text-slate-300 mb-1 block">Full name (optional)</span>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your name"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition"
              />
            </label>

            <label className="block mb-4">
              <span className="text-sm text-slate-300 mb-1 block">Work email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition"
              />
            </label>

            <label className="block mb-4">
              <span className="text-sm text-slate-300 mb-1 block">Password</span>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition"
              />
            </label>

            <label className="block mb-6">
              <span className="text-sm text-slate-300 mb-1 block">Confirm password</span>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition"
              />
            </label>

            {error && (
              <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 font-semibold rounded-lg transition"
              >
                &larr; Back
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition"
              >
                {loading ? "Creating workspace..." : "Create workspace"}
              </button>
            </div>

            <div className="text-center text-sm text-slate-400 mt-6">
              Already have an account?{" "}
              <Link href="/login" className="text-red-400 hover:text-red-300 font-medium">
                Sign in
              </Link>
            </div>
          </form>
        )}

        <p className="text-center text-xs text-slate-500 mt-6">
          Powered by FastAPI + Next.js
        </p>
      </div>
    </div>
  );
}
