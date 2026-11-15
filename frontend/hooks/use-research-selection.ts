"use client";

import { useEffect, useState } from "react";
import {
  DEFAULT_RESEARCH_PREFERENCES,
  readResearchPreferences,
  ResearchPeriod,
} from "@/lib/research-preferences";

export function useResearchSelection() {
  const [code, setCode] = useState(DEFAULT_RESEARCH_PREFERENCES.defaultCode);
  const [period, setPeriod] = useState<ResearchPeriod>(DEFAULT_RESEARCH_PREFERENCES.defaultPeriod);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const preferences = readResearchPreferences();
      setCode(preferences.defaultCode);
      setPeriod(preferences.defaultPeriod);
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  return { code, period, ready, setCode, setPeriod };
}
