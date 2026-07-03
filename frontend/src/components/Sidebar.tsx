"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { getUser, logout } from "@/lib/auth";

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
};

const NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="9" />
        <rect x="14" y="3" width="7" height="5" />
        <rect x="14" y="12" width="7" height="9" />
        <rect x="3" y="16" width="7" height="5" />
      </svg>
    ),
  },
  {
    href: "/transactions",
    label: "Transactions",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="3" y1="6" x2="21" y2="6" />
        <line x1="3" y1="12" x2="21" y2="12" />
        <line x1="3" y1="18" x2="21" y2="18" />
      </svg>
    ),
  },
  {
    href: "/predict",
    label: "Live Predict",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <aside className="w-60 bg-slate-950 border-r border-slate-800 flex flex-col shrink-0">
      {/* Brand + Company */}
      <div className="px-5 py-5 border-b border-slate-800">
        <div className="text-[10px] tracking-[0.2em] text-red-500 font-bold">
          CHIMERA-FD
        </div>
        {user?.company ? (
          <>
            <div className="text-base font-semibold text-white mt-1 truncate" title={user.company.name}>
              {user.company.name}
            </div>
            {user.company.industry && (
              <div className="text-[11px] text-slate-500 truncate" title={user.company.industry}>
                {user.company.industry}
              </div>
            )}
          </>
        ) : (
          <div className="text-sm text-slate-400 mt-0.5">Fraud Detection</div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4">
        {NAV.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm mb-1 transition ${
                active
                  ? "bg-red-500/10 text-red-400 border border-red-500/30"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent"
              }`}
            >
              <span className="opacity-90">{item.icon}</span>
              <span className="font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User + sign out */}
      <div className="px-3 py-4 border-t border-slate-800">
        {user && (
          <div className="px-3 py-2 mb-2">
            <div className="text-xs text-slate-500 uppercase tracking-wider">
              Signed in
            </div>
            <div className="text-sm text-slate-200 truncate">{user.email}</div>
            <div className="text-xs text-slate-500 uppercase tracking-wider mt-0.5">
              {user.role}
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Sign out
        </button>
      </div>
    </aside>
  );
}
