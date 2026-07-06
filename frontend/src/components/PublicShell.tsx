"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Splash } from "./Splash";
import { getUser, isAuthenticated, User } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/features", label: "Features" },
  { href: "/merchants", label: "Live Demo" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
  { href: "/pricing", label: "Pricing" },
];

export function PublicShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [showSplash, setShowSplash] = useState(false);
  const [splashChecked, setSplashChecked] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    setLoggedIn(isAuthenticated());
    setUser(getUser());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (pathname !== "/") {
      setSplashChecked(true);
      return;
    }
    const seen = sessionStorage.getItem("chimera_splash_seen");
    if (!seen) {
      setShowSplash(true);
    }
    setSplashChecked(true);
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function handleSplashDone() {
    sessionStorage.setItem("chimera_splash_seen", "1");
    setShowSplash(false);
  }

  if (!splashChecked) return null;

  return (
    <>
      {showSplash && <Splash onDone={handleSplashDone} />}

      <div className="min-h-screen bg-slate-950 text-slate-100">
        {/* Header */}
        <header
          className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
            scrolled
              ? "bg-slate-950/80 backdrop-blur-lg border-b border-slate-800"
              : "bg-transparent"
          }`}
        >
          <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center text-white font-bold text-sm">
                C
              </div>
              <div>
                <div className="text-lg font-bold font-serif tracking-tight group-hover:text-red-400 transition">
                  CHIMERA-FD
                </div>
                <div className="text-[9px] tracking-widest text-red-500 -mt-1">
                  IBM 2026
                </div>
              </div>
            </Link>

            <nav className="hidden md:flex items-center gap-6">
              {NAV_ITEMS.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`text-sm font-medium transition ${
                      active ? "text-red-400" : "text-slate-300 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="flex items-center gap-3">
              {loggedIn ? (
                <>
                  <div className="hidden sm:flex items-center gap-2 text-xs">
                    <span className="text-slate-500">Signed in as</span>
                    <span className="text-slate-300 font-semibold">
                      {user?.company?.name ?? user?.email?.split("@")[0]}
                    </span>
                  </div>
                  <Link
                    href="/dashboard"
                    className="text-sm font-semibold px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition shadow-lg shadow-red-500/20 hover:shadow-red-500/40 flex items-center gap-2"
                  >
                    Go to dashboard
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12" />
                      <polyline points="12 5 19 12 12 19" />
                    </svg>
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    href="/login"
                    className="text-sm text-slate-300 hover:text-white font-medium transition hidden sm:block"
                  >
                    Sign in
                  </Link>
                  <Link
                    href="/register"
                    className="text-sm font-semibold px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition shadow-lg shadow-red-500/20 hover:shadow-red-500/40"
                  >
                    Get started
                  </Link>
                </>
              )}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="pt-16">{children}</main>

        {/* Footer */}
        <footer className="border-t border-slate-800 bg-slate-950 mt-24">
          <div className="max-w-7xl mx-auto px-6 py-12">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8">
              <div className="col-span-2">
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-red-500 to-red-700 flex items-center justify-center text-white font-bold text-xs">
                    C
                  </div>
                  <div className="text-base font-bold font-serif">CHIMERA-FD</div>
                </div>
                <p className="text-sm text-slate-400 max-w-sm">
                  Cascaded Hybrid Inference with Multi-modal Explanations and
                  Recalibration for Adaptive Fraud Detection.
                </p>
                <p className="text-xs text-slate-500 mt-3">
                  IBM Internship Capstone 2026
                </p>
              </div>

              <div>
                <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-3">
                  Product
                </div>
                <ul className="space-y-2 text-sm">
                  <li>
                    <Link href="/features" className="text-slate-300 hover:text-red-400 transition">
                      Features
                    </Link>
                  </li>
                  <li>
                    <Link href="/pricing" className="text-slate-300 hover:text-red-400 transition">
                      Pricing
                    </Link>
                  </li>
                  {loggedIn ? (
                    <li>
                      <Link href="/dashboard" className="text-slate-300 hover:text-red-400 transition">
                        Dashboard
                      </Link>
                    </li>
                  ) : (
                    <>
                      <li>
                        <Link href="/login" className="text-slate-300 hover:text-red-400 transition">
                          Sign in
                        </Link>
                      </li>
                      <li>
                        <Link href="/register" className="text-slate-300 hover:text-red-400 transition">
                          Get started
                        </Link>
                      </li>
                    </>
                  )}
                </ul>
              </div>

              <div>
                <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-3">
                  Company
                </div>
                <ul className="space-y-2 text-sm">
                  <li>
                    <Link href="/about" className="text-slate-300 hover:text-red-400 transition">
                      About us
                    </Link>
                  </li>
                  <li>
                    <Link href="/contact" className="text-slate-300 hover:text-red-400 transition">
                      Contact
                    </Link>
                  </li>
                  <li>
                    <a
                      href="https://huggingface.co/spaces/undebuggedbit/chimera-fd"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-300 hover:text-red-400 transition"
                    >
                      HF Space
                    </a>
                  </li>
                </ul>
              </div>
            </div>

            <div className="pt-6 border-t border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="text-xs text-slate-500">
                &copy; 2026 CHIMERA-FD Team &middot; Anurag Pandey, Pankaj Singh, Gurnoor Multani, Sanvi Bharadwaj
              </div>
              <div className="flex gap-4 text-xs text-slate-500">
                <span>Powered by FastAPI + Next.js</span>
                <span>&middot;</span>
                <span>LightGBM &middot; SHAP</span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
