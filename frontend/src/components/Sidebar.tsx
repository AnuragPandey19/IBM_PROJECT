"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getUser, logout } from "@/lib/auth";
import { getSidebarCollapsed, setSidebarCollapsed } from "./ThemeInit";
import { Tooltip } from "./Tooltip";

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
};

const APP_NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="9" rx="1.5" />
        <rect x="14" y="3" width="7" height="5" rx="1.5" />
        <rect x="14" y="12" width="7" height="9" rx="1.5" />
        <rect x="3" y="16" width="7" height="5" rx="1.5" />
      </svg>
    ),
  },
  {
    href: "/transactions",
    label: "Transactions",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 6h18" />
        <path d="M3 12h18" />
        <path d="M3 18h18" />
      </svg>
    ),
  },
  {
    href: "/predict",
    label: "Live Predict",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
    ),
  },
  {
    href: "/analytics",
    label: "Analytics",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" />
        <path d="M18 17V9M13 17V5M8 17v-3" />
      </svg>
    ),
  },
];

const SIDEBAR_SECTION_LABEL = process.env.NEXT_PUBLIC_SIDEBAR_SECTION ?? "Fraud Ops";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  // Lazy init so we don't re-read + JSON.parse localStorage on every render.
  const [user] = useState(() => (typeof window !== "undefined" ? getUser() : null));
  // Two-phase mount to avoid hydration flash. Server render + first client
  // render are both `collapsed=false` (matches SSR). Only after mount do we
  // read localStorage and apply the persisted preference. `mounted` gates
  // rendering so the aria-label / width don't flip mid-frame.
  const [collapsed, setCollapsedState] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setCollapsedState(getSidebarCollapsed());
    setMounted(true);
    const handler = (e: Event) => {
      setCollapsedState((e as CustomEvent).detail);
    };
    window.addEventListener("sidebar-toggled", handler);
    return () => window.removeEventListener("sidebar-toggled", handler);
  }, []);

  function toggle() {
    const next = !collapsed;
    setCollapsedState(next);
    setSidebarCollapsed(next);
  }

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  const initials = user?.company?.name
    ? user.company.name.substring(0, 2).toUpperCase()
    : "CF";

  const userInitials = user?.full_name
    ? user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : (user?.email ?? "??").substring(0, 2).toUpperCase();

  return (
    <aside
      // Suppress hydration warning on the outer element only — width is the
      // one attribute whose SSR value legitimately differs from the
      // post-mount client value (see two-phase mount comment above).
      suppressHydrationWarning
      className={`shrink-0 flex flex-col transition-[width] duration-300 ease-out relative`}
      style={{
        width: mounted && collapsed ? "72px" : "260px",
        background: "var(--bg-sidebar)",
        borderRight: "1px solid var(--border-subtle)",
      }}
    >
      {/* Collapse button on right edge */}
      <button
        onClick={toggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="absolute -right-3 top-24 z-30 w-6 h-6 rounded-full flex items-center justify-center glass hover:scale-110 transition-transform shadow-lg"
        style={{ background: "var(--bg-elevated)" }}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`transition-transform duration-300 ${collapsed ? "" : "rotate-180"}`}
          style={{ color: "var(--text-secondary)" }}
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>

      {/* Workspace header */}
      <div className="p-3">
        <Link href="/dashboard" className="block group">
          <div
            className={`flex items-center gap-3 p-2.5 rounded-xl glass glass-hover transition ${
              collapsed ? "justify-center" : ""
            }`}
          >
            <div
              className="w-10 h-10 rounded-xl accent-gradient flex items-center justify-center text-white font-black text-sm shadow-lg shrink-0"
              style={{ boxShadow: "0 8px 24px -8px var(--accent-glow)" }}
            >
              {initials}
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1 animate-fade-in">
                <div
                  className="text-[9px] tracking-[0.18em] font-bold uppercase mb-0.5"
                  style={{ color: "var(--accent-primary)" }}
                >
                  Workspace
                </div>
                <div className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                  {user?.company?.name ?? "CHIMERA-FD"}
                </div>
              </div>
            )}
          </div>
        </Link>
      </div>

      {/* Main nav */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {!collapsed && (
          <div className="text-[10px] tracking-[0.15em] font-semibold uppercase mb-2 px-3 animate-fade-in" style={{ color: "var(--text-faded)" }}>
            {SIDEBAR_SECTION_LABEL}
          </div>
        )}
        <nav>
          {APP_NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const linkEl = (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-1 transition-all duration-200 relative overflow-hidden group ${
                  collapsed ? "justify-center" : ""
                }`}
                style={{
                  background: active ? "var(--accent-bg)" : "transparent",
                  color: active ? "var(--accent-primary)" : "var(--text-secondary)",
                  border: `1px solid ${active ? "rgba(244,63,94,0.25)" : "transparent"}`,
                }}
              >
                {active && (
                  <div
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full"
                    style={{ background: "var(--accent-primary)" }}
                  />
                )}
                <span className="shrink-0 transition-transform group-hover:scale-110">{item.icon}</span>
                {!collapsed && (
                  <span className="font-medium flex-1 animate-fade-in">{item.label}</span>
                )}
                {!collapsed && active && (
                  <span
                    className="text-[9px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded animate-fade-in"
                    style={{ background: "var(--accent-primary)", color: "white" }}
                  >
                    Live
                  </span>
                )}
              </Link>
            );
            return collapsed ? (
              <Tooltip key={item.href} content={item.label} side="right">
                {linkEl}
              </Tooltip>
            ) : (
              linkEl
            );
          })}
        </nav>
      </div>

      {/* User footer */}
      <div className="p-3">
        <div
          className={`rounded-xl glass p-2.5 mb-2 flex items-center gap-2.5 ${
            collapsed ? "justify-center" : ""
          }`}
        >
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0"
            style={{
              background: "linear-gradient(135deg, #475569 0%, #334155 100%)",
              color: "var(--text-primary)",
            }}
          >
            {userInitials}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1 animate-fade-in">
              <div
                className="text-xs font-semibold truncate"
                style={{ color: "var(--text-primary)" }}
                title={user?.email}
              >
                {user?.full_name ?? user?.email?.split("@")[0]}
              </div>
              <div
                className="text-[10px] uppercase tracking-wider truncate"
                style={{ color: "var(--text-faded)" }}
              >
                {user?.role}
              </div>
            </div>
          )}
        </div>

        {collapsed ? (
          <Tooltip content="Sign out" side="right">
            <button
              onClick={handleLogout}
              className="w-full h-9 flex items-center justify-center rounded-lg text-xs transition"
              style={{
                color: "var(--text-muted)",
                background: "transparent",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(244,63,94,0.08)";
                e.currentTarget.style.color = "var(--accent-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--text-muted)";
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </Tooltip>
        ) : (
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition animate-fade-in"
            style={{
              color: "var(--text-muted)",
              background: "transparent",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(244,63,94,0.08)";
              e.currentTarget.style.color = "var(--accent-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-muted)";
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            Sign out
          </button>
        )}
      </div>
    </aside>
  );
}
