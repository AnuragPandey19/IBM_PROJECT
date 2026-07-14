import type { Metadata } from "next";
import { Inter, Fraunces, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeInit } from "@/components/ThemeInit";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const fraunces = Fraunces({
  variable: "--font-serif",
  subsets: ["latin"],
  weight: ["700", "900"],
  display: "swap",
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "CHIMERA-FD — Financial Transaction Fraud Detection",
  description:
    "Cascaded Hybrid Inference with Multi-modal Explanations and Recalibration for Adaptive Fraud Detection.",
};

/**
 * Runs synchronously in the browser BEFORE React hydration. Reads the
 * persisted theme and sets the `data-theme` attribute on `<html>` so
 * CSS variables cascade correctly on the very first paint — no dark→light
 * flash if the user has previously chosen light. Falls back to the OS
 * preference via `prefers-color-scheme` when no explicit choice exists.
 */
const THEME_BOOT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('chimera_theme');
    var theme = stored || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${fraunces.variable} ${jetBrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* Prevents the wrong-theme flash between SSR and hydration. Must run
            before any component renders. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-full flex flex-col">
        <ThemeInit />
        {children}
      </body>
    </html>
  );
}
