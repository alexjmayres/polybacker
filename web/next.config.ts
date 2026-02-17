import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // In production, NEXT_PUBLIC_API_URL points directly to the backend;
    // rewrites only needed for local dev where the API runs on :5001.
    if (process.env.NEXT_PUBLIC_API_URL) {
      return [];
    }
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:5001/api/:path*",
      },
    ];
  },
};

export default nextConfig;
