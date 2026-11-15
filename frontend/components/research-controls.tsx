"use client";

import { FormEvent, useEffect, useId, useState } from "react";
import { ArrowRight, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/research-ui";
import { useFundSearch } from "@/hooks/use-fund-search";
import { RESEARCH_PERIOD_LABELS, RESEARCH_PERIODS, ResearchPeriod } from "@/lib/research-preferences";

const PERIOD_OPTIONS = RESEARCH_PERIODS.map((value) => ({
  value,
  label: RESEARCH_PERIOD_LABELS[value],
}));

export function ResearchControls({
  code,
  period,
  onCodeChange,
  onPeriodChange,
}: {
  code: string;
  period: ResearchPeriod;
  onCodeChange: (code: string) => void;
  onPeriodChange: (period: ResearchPeriod) => void;
}) {
  const inputId = useId();
  const [draft, setDraft] = useState(code);
  const [inputError, setInputError] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const { suggestions, isSearching } = useFundSearch(draft, 5);

  useEffect(() => {
    const timer = window.setTimeout(() => setDraft(code), 0);
    return () => window.clearTimeout(timer);
  }, [code]);

  function selectFund(nextCode: string) {
    onCodeChange(nextCode);
    setDraft(nextCode);
    setInputError("");
    setSearchOpen(false);
  }

  function submitFund(event: FormEvent) {
    event.preventDefault();
    const normalized = draft.trim();
    if (!/^\d{6}$/.test(normalized)) {
      setInputError("请输入 6 位基金代码，例如 161725。");
      return;
    }
    selectFund(normalized);
  }

  return (
    <section className="overview-controls" aria-label="研究对象与区间">
      <form className="overview-fund-form" onSubmit={submitFund}>
        <label htmlFor={inputId}>研究基金</label>
        <div className="overview-search-wrap">
          <div className="overview-search-field">
            <Search size={16} aria-hidden="true" />
            <input
              id={inputId}
              value={draft}
              inputMode="numeric"
              autoComplete="off"
              placeholder="输入 6 位基金代码"
              aria-describedby={inputError ? `${inputId}-error` : undefined}
              onFocus={() => setSearchOpen(true)}
              onChange={(event) => {
                setDraft(event.target.value);
                setSearchOpen(true);
                setInputError("");
              }}
            />
          </div>
          {searchOpen && draft.trim() && (isSearching || suggestions.length > 0) && (
            <div className="overview-suggestions" role="listbox" aria-label="基金搜索结果">
              {isSearching && <p>正在搜索真实基金名录…</p>}
              {suggestions.map((fund) => (
                <button type="button" role="option" aria-selected={fund.code === code} key={fund.code} onClick={() => selectFund(fund.code)}>
                  <span><strong>{fund.name}</strong><small>{fund.code} · {fund.type}</small></span>
                  <ArrowRight size={15} aria-hidden="true" />
                </button>
              ))}
            </div>
          )}
        </div>
        <Button type="submit">切换基金</Button>
        {inputError && <p className="field-error" id={`${inputId}-error`} role="alert">{inputError}</p>}
      </form>
      <SegmentedControl items={PERIOD_OPTIONS} value={period} onChange={onPeriodChange} label="统计区间" />
    </section>
  );
}
