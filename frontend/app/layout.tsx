import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Fund Analyzer · 基金历史数据分析",
  description: "查看基金历史收益、风险、持仓与真实组合记录。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full bg-background text-foreground">
        <Providers>
          <Nav />
          <main className="app-main">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
