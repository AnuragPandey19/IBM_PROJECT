"use client";

import { useState, useEffect, ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Standard hover tooltip that wraps its children in a span. Use this for
 * buttons, icons, small inline elements. Do NOT use around <tr> — for tables,
 * use TableRowTooltip below.
 */
export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
}) {
  const [show, setShow] = useState(false);

  const sideClasses = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          className={`absolute z-50 pointer-events-none animate-fade-in ${sideClasses[side]}`}
        >
          <span
            className="block rounded-lg px-3 py-2 text-xs shadow-2xl whitespace-nowrap"
            style={{
              background: "rgba(15, 15, 25, 0.96)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-default)",
              backdropFilter: "blur(10px)",
            }}
          >
            {content}
          </span>
        </span>
      )}
    </span>
  );
}

/**
 * Floating tooltip that follows the mouse pointer via React Portal.
 * Use this for table rows — rendered to document.body so it doesn't
 * violate HTML nesting rules.
 *
 * Usage:
 *   const [hover, setHover] = useState<HoverState | null>(null);
 *   <tr onMouseEnter={(e) => setHover({ x: e.clientX, y: e.clientY, ... })} ...>
 *   <FloatingTooltip hover={hover}>{content}</FloatingTooltip>
 */
export type FloatingHoverState = { x: number; y: number };

export function FloatingTooltip({
  hover,
  children,
}: {
  hover: FloatingHoverState | null;
  children: ReactNode;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted || !hover) return null;

  // Position tooltip near mouse but clamped to viewport
  const offset = 16;
  const maxWidth = 300;
  const left = Math.min(hover.x + offset, window.innerWidth - maxWidth - 20);
  const top = Math.min(hover.y + offset, window.innerHeight - 200);

  return createPortal(
    <div
      className="fixed z-[100] pointer-events-none animate-fade-in"
      style={{ left, top, maxWidth }}
    >
      <div
        className="rounded-lg p-3 shadow-2xl"
        style={{
          background: "rgba(15, 15, 25, 0.98)",
          color: "var(--text-primary)",
          border: "1px solid var(--border-default)",
          backdropFilter: "blur(20px)",
        }}
      >
        {children}
      </div>
    </div>,
    document.body
  );
}
