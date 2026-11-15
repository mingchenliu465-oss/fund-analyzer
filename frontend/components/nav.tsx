"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  ChevronLeft,
  ChevronRight,
  Compass,
  Database,
  FileText,
  FlaskConical,
  Home,
  LineChart,
  List,
  Menu,
  Scale,
  Search,
  Settings,
  Shield,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useFundSearch } from "@/hooks/use-fund-search";

const navGroups = [
  { label: "工作台", items: [{ href: "/", label: "首页", icon: Home }] },
  {
    label: "市场",
    items: [
      { href: "/discover", label: "市场发现", icon: Compass },
      { href: "/fund", label: "基金搜索", icon: List },
    ],
  },
  {
    label: "研究",
    items: [
      { href: "/performance", label: "表现分析", icon: LineChart },
      { href: "/risk", label: "风险分析", icon: Shield },
      { href: "/data-audit", label: "数据审计", icon: Database },
    ],
  },
  { label: "策略", items: [{ href: "/backtest", label: "回测实验室", icon: FlaskConical }] },
  {
    label: "组合",
    items: [
      { href: "/portfolio", label: "我的组合", icon: BriefcaseBusiness },
      { href: "/insights", label: "组合洞察", icon: Activity },
    ],
  },
  {
    label: "工具",
    items: [
      { href: "/compare", label: "基金对比", icon: Scale },
      { href: "/review", label: "投资复盘", icon: FileText },
      { href: "/workbench", label: "分析工作台", icon: SlidersHorizontal },
    ],
  },
  { label: "设置", items: [{ href: "/settings", label: "偏好设置", icon: Settings }] },
];

export function Nav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const { suggestions, isSearching, isError } = useFundSearch(query, 6);

  useEffect(() => {
    document.documentElement.style.setProperty("--sidebar-width", collapsed ? "72px" : "232px");
  }, [collapsed]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setMobileOpen(false);
      setQuery("");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", close);
    };
  }, [mobileOpen]);

  useEffect(() => {
    const close = (event: PointerEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) setSearchFocused(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, []);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const navContent = (mobile = false) => (
    <>
      <div className="flex h-16 items-center justify-between border-b border-border px-5">
        <Link href="/" className="min-w-0" aria-label="Fund Analyzer 首页">
          <span className="block truncate text-[15px] font-semibold tracking-tight">Fund Analyzer</span>
          {(!collapsed || mobile) && <span className="block text-[11px] text-muted-foreground">Research with Evidence.</span>}
        </Link>
        {mobile && (
          <button type="button" onClick={() => setMobileOpen(false)} className="flex h-11 w-11 items-center justify-center" aria-label="关闭导航">
            <X className="h-5 w-5" />
          </button>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="主导航">
        {navGroups.map((group) => (
          <div key={group.label} className="mb-4">
            {(!collapsed || mobile) && <div className="px-3 pb-1 text-[11px] font-medium text-muted-foreground">{group.label}</div>}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed && !mobile ? item.label : undefined}
                    aria-current={active ? "page" : undefined}
                    className={`flex min-h-10 items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors ${
                      active ? "bg-muted font-semibold text-accent" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    } ${collapsed && !mobile ? "justify-center px-0" : ""}`}
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {(!collapsed || mobile) && <span>{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      {(!collapsed || mobile) && (
        <div className="border-t border-border p-4 text-[11px] leading-relaxed text-muted-foreground">
          历史研究不构成收益预测。数据来源与更新时间见各页面披露。
        </div>
      )}
    </>
  );

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[var(--sidebar-width)] flex-col border-r border-border bg-surface transition-[width] duration-200 lg:flex">
        {navContent()}
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="absolute -right-5 top-20 flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-muted-foreground hover:text-foreground"
          aria-label={collapsed ? "展开侧边栏" : "折叠侧边栏"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/30" onClick={() => setMobileOpen(false)} aria-label="关闭导航菜单" />
          <aside className="relative flex h-full w-[min(84vw,320px)] flex-col bg-surface">{navContent(true)}</aside>
        </div>
      )}

      <header className="fixed inset-x-0 top-0 z-30 flex h-[var(--topbar-height)] items-center gap-2 border-b border-border bg-surface px-3 lg:left-[var(--sidebar-width)] lg:px-6">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="flex h-11 w-11 shrink-0 items-center justify-center lg:hidden"
          aria-label="打开导航"
          aria-expanded={mobileOpen}
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link href="/" className="hidden shrink-0 text-sm font-semibold sm:block lg:hidden">Fund Analyzer</Link>
        <div ref={searchRef} className="relative mx-auto w-full max-w-2xl">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onFocus={() => setSearchFocused(true)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setQuery("");
                setSearchFocused(false);
              }
            }}
            className="h-11 w-full rounded-md border border-border bg-muted pl-10 pr-4 text-base outline-none placeholder:text-muted-foreground focus:border-accent focus:bg-surface md:text-sm"
            placeholder="搜索基金代码或名称"
            aria-label="全站搜索基金代码或名称"
          />
          {searchFocused && query.trim() && (
            <div className="absolute inset-x-0 top-12 border border-border bg-surface py-2">
              {suggestions.length > 0 ? (
                suggestions.map((fund) => (
                  <Link key={fund.code} href={`/fund/${fund.code}`} className="flex min-h-11 items-center justify-between gap-4 px-4 py-2 text-sm hover:bg-muted">
                    <span className="truncate font-medium">{fund.name}</span>
                    <span className="numeric text-xs text-muted-foreground">{fund.code}</span>
                  </Link>
                ))
              ) : (
                <p className="px-4 py-3 text-xs text-muted-foreground">
                  {isSearching ? "正在搜索…" : isError ? "搜索暂时不可用，请稍后重试。" : "暂时没有匹配结果。"}
                </p>
              )}
            </div>
          )}
        </div>
        <Link href="/workbench" className="hidden min-h-11 items-center px-3 text-xs font-medium text-accent hover:underline md:flex">
          <BarChart3 className="mr-1 h-4 w-4" aria-hidden="true" />打开工作台
        </Link>
      </header>
    </>
  );
}
