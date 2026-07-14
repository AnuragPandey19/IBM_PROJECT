"use client";

/**
 * Global error boundary for the App Router. Next.js renders this when any
 * child component throws during rendering. Without it, the entire app
 * white-screens with no recovery.
 */
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // In production we'd ship this to Sentry / Datadog. For now, console is fine.
    // eslint-disable-next-line no-console
    console.error("Unhandled render error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100 px-6">
      <div className="max-w-md w-full text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-400">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-white mb-2" style={{ fontFamily: "var(--font-serif)" }}>
          Something broke
        </h1>
        <p className="text-sm text-slate-400 mb-6">
          The dashboard hit an unexpected error. This is a bug — please report it.
          {error?.digest ? (
            <span className="block mt-2 font-mono text-xs text-slate-500">
              Reference: {error.digest}
            </span>
          ) : null}
        </p>
        <div className="flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="px-5 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-sm shadow-lg shadow-red-500/20 transition"
          >
            Try again
          </button>
          <a
            href="/"
            className="px-5 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold text-sm transition"
          >
            Home
          </a>
        </div>
        {process.env.NODE_ENV === "development" && (
          <pre className="mt-6 p-3 text-[10px] text-left rounded-lg bg-slate-900 border border-slate-800 text-slate-400 overflow-auto max-h-48 font-mono">
            {error.message}
            {"\n"}
            {error.stack}
          </pre>
        )}
      </div>
    </div>
  );
}
