/**
 * Portal preferences persisted in localStorage and consumed by Analyzer/Settings.
 * Only keys that have a real UI consumer belong here — no fake backend settings.
 */

export type AnalyzerLanguage = "th" | "en";
export type HistorySort = "newest" | "oldest";
export type PortalTheme = "light" | "dark" | "system";

export type PortalPreferences = {
  analyzerLanguage: AnalyzerLanguage;
  historySort: HistorySort;
  /** Mirrored from ThemeProvider storage for Settings UI; ThemeProvider remains source of truth for apply. */
  theme: PortalTheme;
};

export const PREF_KEYS = {
  analyzerLanguage: "eims.pref.analyzerLanguage",
  historySort: "eims.pref.historySort",
  theme: "eims-theme",
} as const;

const DEFAULTS: PortalPreferences = {
  /** Analysis report output language only — Portal UI is English-first. */
  analyzerLanguage: "en",
  historySort: "newest",
  theme: "system",
};

function readRaw(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore quota / private mode */
  }
}

export function readPortalPreferences(): PortalPreferences {
  const lang = readRaw(PREF_KEYS.analyzerLanguage);
  const sort = readRaw(PREF_KEYS.historySort);
  const theme = readRaw(PREF_KEYS.theme);
  return {
    analyzerLanguage: lang === "en" || lang === "th" ? lang : DEFAULTS.analyzerLanguage,
    historySort: sort === "oldest" || sort === "newest" ? sort : DEFAULTS.historySort,
    theme: theme === "light" || theme === "dark" || theme === "system" ? theme : DEFAULTS.theme,
  };
}

export function writePortalPreferences(patch: Partial<PortalPreferences>): PortalPreferences {
  const next = { ...readPortalPreferences(), ...patch };
  writeRaw(PREF_KEYS.analyzerLanguage, next.analyzerLanguage);
  writeRaw(PREF_KEYS.historySort, next.historySort);
  writeRaw(PREF_KEYS.theme, next.theme);
  return next;
}

/** Inventory for Settings docs / acceptance (source-backed). */
export const PREFERENCE_INVENTORY = [
  {
    name: "analyzerLanguage",
    source: "localStorage eims.pref.analyzerLanguage",
    default: "th",
    allowed: "th | en",
    runtime: true,
    restart: false,
    consumer: "Log Analyzer upload language select",
    safeUi: true,
  },
  {
    name: "historySort",
    source: "localStorage eims.pref.historySort",
    default: "newest",
    allowed: "newest | oldest",
    runtime: true,
    restart: false,
    consumer: "AnalyzerHistoryList default sort",
    safeUi: true,
  },
  {
    name: "theme",
    source: "localStorage eims-theme (ThemeProvider)",
    default: "system",
    allowed: "light | dark | system",
    runtime: true,
    restart: false,
    consumer: "ThemeProvider / layout FOUC script",
    safeUi: true,
  },
] as const;
