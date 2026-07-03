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
};

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  function validate(): string | null {
    if (!email.trim()) return "Email is required";
    if (!password) return "Password is required";
    if (password.length < 8) return "Password must be at least 8 characters";
    if (password !== confirmPassword) return "Passwords do not match";
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const v = validate();
    if (v) {
      setError(v);
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
          role: "analyst", // Public signups always create analyst role. Admin must be provisioned via CLI.
        },
        auth: false,
      });
      setSuccess(true);
      // Redirect to login after brief pause so the success message is visible
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setError("An account with this email already exists. Try signing in.");
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
          <h1 className="text-2xl font-bold text-white mb-2">Account created</h1>
          <p className="text-slate-400 mb-6">Redirecting to sign in&hellip;</p>
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

        <form
          onSubmit={handleSubmit}
          className="bg-slate-800/60 backdrop-blur border border-slate-700 rounded-2xl p-8 shadow-2xl"
        >
          <h2 className="text-xl font-semibold text-white mb-2">Create account</h2>
          <p className="text-xs text-slate-400 mb-6">
            New analysts sign up here. Admin accounts are provisioned separately.
          </p>

          <label className="block mb-4">
            <span className="text-sm text-slate-300 mb-1 block">Full name (optional)</span>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Anurag Pandey"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-red-500 transition"
            />
          </label>

          <label className="block mb-4">
            <span className="text-sm text-slate-300 mb-1 block">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
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

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:opacity-60 text-white font-semibold py-2.5 rounded-lg transition"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>

          <div className="text-center text-sm text-slate-400 mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-red-400 hover:text-red-300 font-medium">
              Sign in
            </Link>
          </div>
        </form>

        <p className="text-center text-xs text-slate-500 mt-6">
          Powered by FastAPI + Next.js
        </p>
      </div>
    </div>
  );
}
