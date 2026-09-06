import type { NextConfig } from "next";

// 后端 API 目标地址：默认 8000（与 README / backend/main.py 保持一致），
// 可通过 NEXT_PUBLIC_API_URL 覆盖。避免端口在配置中硬编码漂移。
const API_TARGET =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

const nextConfig: NextConfig = {
  // 指定 Turbopack 工作区根目录，避免多 lockfile 警告
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
