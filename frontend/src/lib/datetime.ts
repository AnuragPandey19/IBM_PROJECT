/**
 * Shared datetime helpers.
 *
 * The core problem this file solves: the backend sometimes emits ISO strings
 * without a `Z` suffix (SQLite stores tz-naive datetimes). JavaScript's
 * `new Date(iso)` treats a no-Z string as LOCAL time, which is wrong — the
 * value is UTC, and interpreting it as local shifts the displayed time by
 * the browser's UTC offset.
 *
 * Every place that parses a backend timestamp should use `parseServerIso`
 * from this file, NOT `new Date(iso)` directly.
 */

/** Parse an ISO string that the backend produced. Assumes UTC when the string
 *  lacks an explicit timezone marker. */
export function parseServerIso(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const s = String(iso).trim();
  if (!s) return null;
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/i.test(s);
  const d = new Date(hasTz ? s : s + "Z");
  return isNaN(d.getTime()) ? null : d;
}

/** Format a backend timestamp using the browser's locale + timezone. */
export function fmtDateTime(iso: string | null | undefined): string {
  const d = parseServerIso(iso);
  if (!d) return "—";
  return d.toLocaleString();
}

/** Two-line "when" format used in transaction tables:
 *  - `primary`: "Today, 2:14 pm" / "Yesterday, 8:05 am" / "6 Jul, 10:23 am"
 *  - `full`: full timestamp with weekday + timezone (used as `title` tooltip). */
export function fmtWhen(iso: string | null | undefined): { primary: string; full: string } {
  const d = parseServerIso(iso);
  if (!d) return { primary: "—", full: "" };
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    d.getFullYear() === yesterday.getFullYear() &&
    d.getMonth() === yesterday.getMonth() &&
    d.getDate() === yesterday.getDate();
  const timeStr = d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
  let primary: string;
  if (sameDay) primary = `Today, ${timeStr}`;
  else if (isYesterday) primary = `Yesterday, ${timeStr}`;
  else
    primary = d.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
    }) + `, ${timeStr}`;
  const full = d.toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
    timeZoneName: "short",
  });
  return { primary, full };
}

/** "just now" / "3m ago" / "2h ago" / short date. */
export function timeAgo(iso: string | null | undefined): string {
  const d = parseServerIso(iso);
  if (!d) return "—";
  const seconds = Math.floor((Date.now() - d.getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return d.toLocaleDateString();
}
