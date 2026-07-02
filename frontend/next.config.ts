import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for single-container Docker deployment on Hugging Face Spaces.
  // FastAPI serves the generated /out directory alongside API routes.
  output: "export",

  // Emitted assets live under /out — FastAPI mounts this at "/"
  distDir: ".next",

  // Trailing slash keeps folder-style URLs so /login/ maps to /login/index.html
  trailingSlash: true,

  // next/image optimization requires a running Node server. Disabled for static export.
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
