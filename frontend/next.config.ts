import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The dashboard talks to the FastAPI backend; proxy /api to it in dev so the
  // browser stays same-origin (no CORS credentials complexity).
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      // The health probes sit outside the /api prefix on the backend, so they
      // need their own rule — without it they resolve against Next and 404.
      { source: "/health", destination: `${backend}/health` },
      { source: "/health/:path*", destination: `${backend}/health/:path*` },
    ];
  },
};

export default nextConfig;
