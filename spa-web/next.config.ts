import type { NextConfig } from "next";

const bffOrigin = process.env.BFF_PUBLIC_ORIGIN || "http://127.0.0.1:3001";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${bffOrigin}/api/backend/:path*`,
      },
    ];
  },
};

export default nextConfig;

