export const RESEARCH_PERIODS = ["1m", "3m", "6m", "1y", "3y", "all"] as const;

export type ResearchPeriod = (typeof RESEARCH_PERIODS)[number];

export const RESEARCH_PERIOD_LABELS: Record<ResearchPeriod, string> = {
  "1m": "近1月",
  "3m": "近3月",
  "6m": "近6月",
  "1y": "近1年",
  "3y": "近3年",
  all: "成立以来",
};

export type ResearchPreferences = {
  defaultCode: string;
  defaultPeriod: ResearchPeriod;
};

export const DEFAULT_RESEARCH_PREFERENCES: ResearchPreferences = {
  defaultCode: "161725",
  defaultPeriod: "1y",
};

const STORAGE_KEY = "fund-analyzer.research-preferences";

export function readResearchPreferences(): ResearchPreferences {
  if (typeof window === "undefined") return DEFAULT_RESEARCH_PREFERENCES;
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null") as Partial<ResearchPreferences> | null;
    const defaultCode = typeof value?.defaultCode === "string" && /^\d{6}$/.test(value.defaultCode)
      ? value.defaultCode
      : DEFAULT_RESEARCH_PREFERENCES.defaultCode;
    const defaultPeriod = RESEARCH_PERIODS.includes(value?.defaultPeriod as ResearchPeriod)
      ? value?.defaultPeriod as ResearchPeriod
      : DEFAULT_RESEARCH_PREFERENCES.defaultPeriod;
    return { defaultCode, defaultPeriod };
  } catch {
    return DEFAULT_RESEARCH_PREFERENCES;
  }
}

export function writeResearchPreferences(preferences: ResearchPreferences): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  window.dispatchEvent(new Event("research-preferences-changed"));
}
