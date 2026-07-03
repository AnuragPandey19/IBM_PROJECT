"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { getUser, isAuthenticated } from "@/lib/auth";
import { getTheme, toggleTheme } from "./ThemeInit";
import { Sidebar } from "./Sidebar";
import { Tooltip } from "./Tooltip";
import { NotificationPanel } from "./NotificationPanel";

const EXPLORE_NAV = [
  { href: "/features", label: "Features" },
  { href: "/about", label: "About" },
  { href: "/pricing", label: "Pricing" },
  { href: "/contact", label: "Contact" },
];

export function AppShell({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [theme, setThemeState] = useState<"dark" | "light">("dark");
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
      return;
    }
    setReady(true);
    setThemeState(getTheme());
  }, [router]);

  if (!ready) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "var(--bg-base)", color: "var(--text-muted)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-2 h-2 rounded-full animate-pulse-glow"
            style={{ background: "var(--accent-primary)" }}
          />
          <span className="text-sm">Loading...</span>
        </div>
      </div>
    );
  }

  const user = getUser();

  function handleThemeToggle() {
    const next = toggleTheme();
    setThemeState(next);
  }

  const userInitials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : (user?.email ?? "??").substring(0, 2).toUpperCase();

  return (
    <div
      className="min-h-screen flex"
      style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}
    >
      <Sidebar />
      <main className="flex-1 min-w-0 flex flex-col">
        <header
          className="sticky top-0 z-20"
          style={{
            background: "var(--bg-topbar)",
            backdropFilter: "blur(20px) saturate(180%)",
            WebkitBackdropFilter: "blur(20px) saturate(180%)",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          {/* Row 1: Brand LEFT, Explore nav + controls RIGHT */}
          <div
            className="h-14 flex items-center justify-between px-6"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <Link href="/" className="flex items-center gap-2.5 group">
              <div
                className="w-8 h-8 rounded-lg accent-gradient flex items-center justify-center text-white font-black text-sm shadow-lg"
                style={{ boxShadow: "0 4px 12px -4px var(--accent-glow)" }}
              >
                C
              </div>
              <div className="leading-tight">
                <div
                  className="text-sm font-black tracking-tight group-hover:opacity-80 transition"
                  style={{
                    color: "var(--text-primary)",
                    fontFamily: "var(--font-serif)",
                  }}
                >
                  CHIMERA-FD
                </div>
                <div
                  className="text-[9px] tracking-[0.2em] font-semibold uppercase"
                  style={{ color: "var(--accent-primary)" }}
                >
                  IBM 2026
                </div>
              </div>
            </Link>

            <div className="flex items-center gap-4">
              <nav className="hidden md:flex items-center gap-1">
                {EXPLORE_NAV.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="text-sm font-medium px-3 py-1.5 rounded-lg transition"
                      style={{
                        color: active ? "var(--accent-primary)" : "var(--text-muted)",
                        background: active ? "var(--accent-bg)" : "transparent",
                      }}
                      onMouseEnter={(e) => {
                        if (!active) {
                          e.currentTarget.style.background = "var(--bg-glass)";
                          e.currentTarget.style.color = "var(--text-primary)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!active) {
                          e.currentTarget.style.background = "transparent";
                          e.currentTarget.style.color = "var(--text-muted)";
                        }
                      }}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </nav>

              <div
                className="h-5 w-px hidden md:block"
                style={{ background: "var(--border-subtle)" }}
              />

              <div className="flex items-center gap-2">
                {/* Theme */}
                <Tooltip content={theme === "dark" ? "Switch to light" : "Switch to dark"} side="bottom">
                  <button
                    onClick={handleThemeToggle}
                    className="w-9 h-9 rounded-lg flex items-center justify-center transition glass glass-hover"
                    aria-label="Toggle theme"
                  >
                    {theme === "dark" ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-secondary)" }}>
                        <circle cx="12" cy="12" r="4" />
                        <path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32 1.41-1.41" />
                      </svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-secondary)" }}>
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                      </svg>
                    )}
                  </button>
                </Tooltip>

                {/* Notifications */}
                <div className="relative">
                  <Tooltip content="Notifications" side="bottom">
                    <button
                      onClick={() => setNotifOpen(!notifOpen)}
                      className="w-9 h-9 rounded-lg flex items-center justify-center transition glass glass-hover relative"
                      aria-label="Notifications"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--text-secondary)" }}>
                        <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
                        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
                      </svg>
                      {unreadCount > 0 && (
                        <span
                          className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full text-[9px] font-bold text-white flex items-center justify-center"
                          style={{ background: "var(--accent-primary)", boxShadow: "0 0 8px var(--accent-glow)" }}
                        >
                          {unreadCount > 9 ? "9+" : unreadCount}
                        </span>
                      )}
                    </button>
                  </Tooltip>
                  <NotificationPanel
                    open={notifOpen}
                    onClose={() => setNotifOpen(false)}
                    onCountChange={setUnreadCount}
                  />
                </div>

                {/* User avatar → /profile */}
                <Tooltip content={`${user?.email ?? ""} — View profile`} side="bottom">
                  <Link
                    href="/profile"
                    className="w-9 h-9 rounded-lg accent-gradient flex items-center justify-center text-white font-bold text-xs shadow-md transition hover:scale-105"
                    style={{ boxShadow: "0 4px 12px -2px var(--accent-glow)" }}
                  >
                    {userInitials}
                  </Link>
                </Tooltip>
              </div>
            </div>
          </div>

          {/* Row 2: Breadcrumb + Page Title + Actions */}
          <div className="px-6 py-4 flex items-end justify-between gap-4 flex-wrap animate-fade-in">
            <div className="min-w-0">
              <div
                className="flex items-center gap-1.5 text-xs mb-1"
                style={{ color: "var(--text-faded)" }}
              >
                <span
                  className="font-bold tracking-widest uppercase"
                  style={{ color: "var(--accent-primary)" }}
                >
                  {user?.company?.name ?? "Workspace"}
                </span>
                <span>/</span>
                <span style={{ color: "var(--text-secondary)" }}>{title}</span>
              </div>
              <h1
                className="text-2xl font-bold tracking-tight leading-tight"
                style={{
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-serif)",
                }}
              >
                {title}
              </h1>
              {subtitle && (
                <div className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                  {subtitle}
                </div>
              )}
            </div>
            {actions && (
              <div className="flex items-center gap-2 shrink-0">{actions}</div>
            )}
          </div>
        </header>

        <div className="flex-1 px-6 py-6 overflow-auto animate-fade-in">{children}</div>
      </main>
    </div>
  );
}
