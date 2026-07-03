"use client";

import { useEffect, useState } from "react";

/**
 * Netflix-style intro splash: full-screen dark background, CHIMERA-FD name
 * animates in with letter-by-letter reveal, then a subtle red pulse before
 * fading to expose the underlying page. Runs once per session.
 */
export function Splash({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<"reveal" | "hold" | "fade">("reveal");

  useEffect(() => {
    const t1 = setTimeout(() => setPhase("hold"), 1600);
    const t2 = setTimeout(() => setPhase("fade"), 2600);
    const t3 = setTimeout(() => onDone(), 3400);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [onDone]);

  const letters = "CHIMERA-FD".split("");

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center bg-black transition-opacity duration-700 ${
        phase === "fade" ? "opacity-0 pointer-events-none" : "opacity-100"
      }`}
    >
      {/* Radial glow */}
      <div className="absolute inset-0 bg-gradient-radial from-red-950/40 via-black to-black pointer-events-none" />

      {/* Grid pattern */}
      <div
        className="absolute inset-0 opacity-20 pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(220,38,38,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(220,38,38,0.15) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      {/* Center content */}
      <div className="relative flex flex-col items-center">
        {/* Small tag */}
        <div
          className={`text-[10px] tracking-[0.4em] text-red-500 font-bold mb-4 transition-all duration-700 ${
            phase === "reveal" ? "opacity-0 translate-y-4" : "opacity-100 translate-y-0"
          }`}
        >
          IBM INTERNSHIP &middot; 2026
        </div>

        {/* Big title with per-letter reveal */}
        <h1 className="font-serif font-black text-6xl md:text-8xl tracking-tight flex">
          {letters.map((ch, i) => (
            <span
              key={i}
              className="inline-block chimera-letter"
              style={{
                animationDelay: `${i * 90}ms`,
                color: ch === "-" ? "#dc2626" : "#ffffff",
              }}
            >
              {ch === " " ? " " : ch}
            </span>
          ))}
        </h1>

        {/* Underline pulse */}
        <div
          className={`h-1 mt-6 bg-gradient-to-r from-transparent via-red-500 to-transparent transition-all duration-1000 ${
            phase === "reveal" ? "w-0 opacity-0" : "w-80 opacity-100"
          }`}
        />

        {/* Tagline */}
        <div
          className={`text-slate-400 text-sm md:text-base mt-6 tracking-wide transition-all duration-1000 delay-500 ${
            phase === "reveal" ? "opacity-0 translate-y-2" : "opacity-100 translate-y-0"
          }`}
        >
          Financial Transaction Fraud Detection
        </div>
      </div>

      <style jsx>{`
        .chimera-letter {
          opacity: 0;
          transform: translateY(20px);
          animation: revealChar 700ms cubic-bezier(0.2, 0.7, 0.2, 1) forwards;
          text-shadow: 0 0 40px rgba(220, 38, 38, 0.3);
        }
        @keyframes revealChar {
          0% {
            opacity: 0;
            transform: translateY(20px) scale(1.2);
            filter: blur(8px);
          }
          60% {
            opacity: 1;
            transform: translateY(-4px) scale(1);
            filter: blur(0);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
            filter: blur(0);
          }
        }
      `}</style>
    </div>
  );
}
