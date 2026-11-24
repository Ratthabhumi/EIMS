"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Settings, Activity, SlidersHorizontal } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";
import {
  readPortalPreferences,
  writePortalPreferences,
  type PortalTheme,
} from "@/lib/portal-preferences";

/**
 * English-first Settings landing: only genuine browser preferences.
 * Analysis output language lives on Analyzer. Runtime health lives under Observability / diagnostics.
 */
export default function SettingsPage() {
  const { setTheme } = useTheme();
  const [prefs, setPrefs] = useState(() => readPortalPreferences());
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    setPrefs(readPortalPreferences());
  }, []);

  const applyTheme = (theme: PortalTheme) => {
    const next = writePortalPreferences({ theme });
    setPrefs(next);
    setTheme(theme);
    setSaveMsg("Theme saved. Applies immediately.");
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold text-eims-text flex items-center gap-2.5">
          <Settings className="w-7 h-7 text-eims-info dark:text-sky-400" />
          Settings
        </h1>
        <p className="text-eims-text-secondary text-sm mt-1">
          Browser preferences for this session.
        </p>
      </div>

      <section className="bg-eims-surface border border-eims-border rounded-xl p-6 shadow-sm space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-eims-border">
          <SlidersHorizontal className="w-5 h-5 text-eims-accent" />
          <h2 className="text-base font-semibold text-eims-text">Theme</h2>
        </div>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-eims-text-secondary uppercase tracking-wider">Preference</span>
          <select
            className="w-full max-w-xs px-3 py-2 text-sm rounded-lg border border-eims-border bg-eims-bg text-eims-text"
            value={prefs.theme}
            onChange={(e) => applyTheme(e.target.value as PortalTheme)}
          >
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
          <span className="text-[11px] text-eims-text-muted">Stored in this browser (localStorage).</span>
        </label>
        {saveMsg ? <p role="status" className="text-xs text-emerald-700 dark:text-emerald-400">{saveMsg}</p> : null}
      </section>

      <p className="text-sm text-eims-text-secondary">
        <Activity className="w-4 h-4 inline-block mr-1.5 align-text-bottom text-eims-info dark:text-sky-400" />
        <Link href="/observability" className="font-medium text-eims-accent hover:underline">
          Runtime Health / Observability
        </Link>
      </p>
    </div>
  );
}
