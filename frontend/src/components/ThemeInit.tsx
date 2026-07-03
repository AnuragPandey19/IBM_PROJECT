"use client";

import { useEffect } from "react";

/**
 * Runs once on mount and reads any persisted theme + sidebar preferences
 * from localStorage. Applied to <html> as data attributes so CSS variables
 * cascade globally without prop drilling.
 */
export function ThemeInit() {
  useEffect(() => {
    const theme = localStorage.getItem("chimera_theme") ?? "dark";
    document.documentElement.setAttribute("data-theme", theme);
  }, []);
  return null;
}

// -------- Helpers used from anywhere --------

export function getTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  return (localStorage.getItem("chimera_theme") as "dark" | "light" | null) ?? "dark";
}

export function setTheme(theme: "dark" | "light") {
  if (typeof window === "undefined") return;
  localStorage.setItem("chimera_theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
  // Broadcast so components can react
  window.dispatchEvent(new CustomEvent("theme-changed", { detail: theme }));
}

export function toggleTheme(): "dark" | "light" {
  const next = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}

export function getSidebarCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("chimera_sidebar_collapsed") === "1";
}

export function setSidebarCollapsed(collapsed: boolean) {
  if (typeof window === "undefined") return;
  localStorage.setItem("chimera_sidebar_collapsed", collapsed ? "1" : "0");
  window.dispatchEvent(new CustomEvent("sidebar-toggled", { detail: collapsed }));
}
