import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 指定 Turbopack 工作区根目录，避免多 lockfile 警告
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8006/api/:path*",
      },
    ];
  },
};

export default nextConfig;
