"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";

type Notification = {
  id: string;
  type: "high_risk" | "review_queue" | "block" | "new_member";
  title: string;
  body: string;
  severity: "info" | "warning" | "critical";
  created_at: string;
  link: string | null;
};

type NotificationList = {
  items: Notification[];
  unread_count: number;
};

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

function severityStyle(sev: string) {
  if (sev === "critical") return { bg: "rgba(239,68,68,0.12)", border: "rgba(239,68,68,0.3)", text: "#f87171" };
  if (sev === "warning") return { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.3)", text: "#fbbf24" };
  return { bg: "rgba(59,130,246,0.12)", border: "rgba(59,130,246,0.3)", text: "#60a5fa" };
}

function IconFor({ type }: { type: string }) {
  if (type === "block") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
      </svg>
    );
  }
  if (type === "review_queue") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    );
  }
  if (type === "new_member") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="8.5" cy="7" r="4" />
        <line x1="20" y1="8" x2="20" y2="14" />
        <line x1="23" y1="11" x2="17" y2="11" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
    </svg>
  );
}

export function NotificationPanel({
  open,
  onClose,
  onCountChange,
}: {
  open: boolean;
  onClose: () => void;
  onCountChange?: (count: number) => void;
}) {
  const router = useRouter();
  const [data, setData] = useState<NotificationList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const panelRef = useRef<HTMLDivElement>(null);

  // Load read IDs from localStorage on first mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem("chimera_read_notifs");
      if (raw) setReadIds(new Set(JSON.parse(raw)));
    } catch {}
  }, []);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<NotificationList>("/api/notifications");
      setData(res);
      const unread = res.items.filter((n) => !readIds.has(n.id)).length;
      onCountChange?.(unread);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  // Fetch when opened & on mount for badge
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Delay to avoid immediate close on toggle click
    const t = setTimeout(() => document.addEventListener("mousedown", handler), 100);
    return () => {
      clearTimeout(t);
      document.removeEventListener("mousedown", handler);
    };
  }, [open, onClose]);

  const markAllRead = () => {
    if (!data) return;
    const ids = new Set(readIds);
    data.items.forEach((n) => ids.add(n.id));
    setReadIds(ids);
    localStorage.setItem("chimera_read_notifs", JSON.stringify([...ids]));
    onCountChange?.(0);
  };

  const markRead = (id: string) => {
    if (readIds.has(id)) return;
    const ids = new Set(readIds);
    ids.add(id);
    setReadIds(ids);
    localStorage.setItem("chimera_read_notifs", JSON.stringify([...ids]));
    if (data) {
      const unread = data.items.filter((n) => !ids.has(n.id)).length;
      onCountChange?.(unread);
    }
  };

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-11 w-96 rounded-xl glass shadow-2xl overflow-hidden animate-fade-in z-50"
      style={{ background: "rgba(15,15,25,0.98)", backdropFilter: "blur(24px)" }}
    >
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
        <div>
          <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Notifications</div>
          <div className="text-[10px] uppercase tracking-widest" style={{ color: "var(--text-faded)" }}>
            {data ? `${data.items.length} recent event${data.items.length === 1 ? "" : "s"}` : "Loading…"}
          </div>
        </div>
        {data && data.items.length > 0 && (
          <button
            onClick={markAllRead}
            className="text-xs font-medium transition"
            style={{ color: "var(--accent-primary)" }}
          >
            Mark all read
          </button>
        )}
      </div>

      <div className="max-h-96 overflow-y-auto">
        {loading && !data && (
          <div className="p-6 text-center text-xs" style={{ color: "var(--text-muted)" }}>Loading…</div>
        )}
        {error && (
          <div className="p-6 text-center text-xs" style={{ color: "#f87171" }}>{error}</div>
        )}
        {data && data.items.length === 0 && !loading && (
          <div className="p-8 text-center">
            <div className="w-12 h-12 rounded-full mx-auto mb-3 flex items-center justify-center" style={{ background: "var(--bg-glass)" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "var(--text-muted)" }}>
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <div className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>You&apos;re all caught up!</div>
            <div className="text-xs mt-1" style={{ color: "var(--text-faded)" }}>No new notifications right now.</div>
          </div>
        )}
        {data && data.items.map((n) => {
          const s = severityStyle(n.severity);
          const isRead = readIds.has(n.id);
          const Body = (
            <div
              className="px-4 py-3 flex items-start gap-3 transition cursor-pointer"
              style={{
                borderBottom: "1px solid var(--border-subtle)",
                background: isRead ? "transparent" : "var(--bg-glass)",
                opacity: isRead ? 0.7 : 1,
              }}
              onClick={() => markRead(n.id)}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-glass-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = isRead ? "transparent" : "var(--bg-glass)")}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: s.bg, border: `1px solid ${s.border}`, color: s.text }}
              >
                <IconFor type={n.type} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2 mb-0.5">
                  <div className="text-xs font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                    {n.title}
                  </div>
                  {!isRead && (
                    <span className="w-1.5 h-1.5 rounded-full shrink-0 mt-1" style={{ background: "var(--accent-primary)" }} />
                  )}
                </div>
                <div className="text-[11px] leading-snug" style={{ color: "var(--text-muted)" }}>
                  {n.body}
                </div>
                <div className="text-[10px] mt-1" style={{ color: "var(--text-faded)" }}>
                  {timeAgo(n.created_at)}
                </div>
              </div>
            </div>
          );
          return n.link ? (
            <Link key={n.id} href={n.link} onClick={onClose}>
              {Body}
            </Link>
          ) : (
            <div key={n.id}>{Body}</div>
          );
        })}
      </div>
    </div>
  );
}
