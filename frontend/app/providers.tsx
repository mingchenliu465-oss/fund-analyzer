"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // 默认 staleTime: 1 分钟，各查询可覆盖
        staleTime: 60 * 1000,
        // 窗口重新聚焦时不自动重新请求（避免不必要的刷新）
        refetchOnWindowFocus: false,
        // 数据服务已有缓存/降级；自动重试只会让慢网络重复占用资源。
        retry: 0,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient() {
  // SSR: 每次请求新建 QueryClient，避免跨请求状态泄漏
  if (typeof window === "undefined") {
    return makeQueryClient();
  }
  // 浏览器：复用同一个 QueryClient 实例，保持缓存
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient();
  }
  return browserQueryClient;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(getQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
