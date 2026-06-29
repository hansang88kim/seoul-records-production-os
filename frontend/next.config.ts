import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The Studio Console is a local desktop-first app; keep builds lean.
  poweredByHeader: false,
};

export default nextConfig;
