"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { BarChart3, PieChart, FileText, Home, Scale, Menu, X, Sparkles } from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/", label: "首页", icon: Home },
  { href: "/fund", label: "基金分析", icon: BarChart3 },
  { href: "/portfolio", label: "我的组合", icon: PieChart },
  { href: "/insights", label: "组合洞察", icon: Sparkles },
  { href: "/compare", label: "基金对比", icon: Scale },
  { href: "/review", label: "投资复盘", icon: FileText },
];

export function Nav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="fixed left-0 top-0 z-40 hidden h-full w-56 flex-col border-r border-border/60 bg-background lg:flex">
        <div className="flex h-16 items-center gap-2.5 px-5">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
              <span className="text-sm font-semibold text-background">智</span>
            </div>
            <span className="text-lg font-medium tracking-tight">智投</span>
          </Link>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3 py-4">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive(item.href)
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
              {isActive(item.href) && (
                <motion.div
                  layoutId="activeSidebarNav"
                  className="absolute inset-0 -z-10 rounded-xl bg-muted"
                  transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                />
              )}
            </Link>
          ))}
        </nav>

        <div className="border-t border-border/60 p-4">
          <div className="rounded-xl bg-muted/40 p-3">
            <div className="text-xs font-medium">Fund Analyzer</div>
            <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
              数据来自 akshare 公开接口，仅供参考。
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur-xl lg:hidden">
        <div className="mx-auto flex h-14 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground">
              <span className="text-sm font-semibold text-background">智</span>
            </div>
            <span className="text-lg font-medium tracking-tight">智投</span>
          </Link>

          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground hover:bg-muted"
            aria-label="切换导航"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {mobileOpen && (
          <nav className="border-t border-border/60 px-3 py-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium ${
                  isActive(item.href)
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:bg-muted/50"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            ))}
          </nav>
        )}
      </header>
    </>
  );
}
