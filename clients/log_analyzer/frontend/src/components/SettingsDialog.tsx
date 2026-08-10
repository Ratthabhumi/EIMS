"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Settings } from "lucide-react";
import { AppSettings } from "@/lib/types";
import { DEFAULT_SETTINGS, saveSettings } from "@/lib/settings";
import { t } from "@/lib/i18n";

interface SettingsDialogProps {
  settings: AppSettings;
  onSave: (settings: AppSettings) => void;
}

export function SettingsDialog({ settings, onSave }: SettingsDialogProps) {
  const [draft, setDraft] = useState<AppSettings>(settings);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (open) queueMicrotask(() => setDraft(settings));
  }, [open, settings]);

  const handleSave = () => {
    const normalized = saveSettings(draft);
    onSave(normalized);
    setOpen(false);
  };

  const handleReset = () => {
    setDraft(DEFAULT_SETTINGS);
  };

  const lang = draft.language;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className="cursor-pointer hover:text-blue-200 flex items-center gap-1">
        <Settings className="w-4 h-4" /> {t(settings.language, "settings")}
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-white dark:bg-gray-800">
        <DialogHeader>
          <DialogTitle className="text-gray-800 dark:text-gray-100">{t(lang, "settingsTitle")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t(lang, "apiUrl")}</label>
            <Input
              type="url"
              value={draft.apiUrl}
              onChange={(e) => setDraft({ ...draft, apiUrl: e.target.value })}
              placeholder="http://localhost:8000"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t(lang, "language")}</label>
            <select
              className="w-full border border-gray-200 dark:border-gray-600 rounded-md px-3 py-2 text-sm bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200"
              value={draft.language}
              onChange={(e) => setDraft({ ...draft, language: e.target.value as AppSettings["language"] })}
            >
              <option value="th">ไทย (Thai)</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t(lang, "theme")}</label>
            <select
              className="w-full border border-gray-200 dark:border-gray-600 rounded-md px-3 py-2 text-sm bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200"
              value={draft.theme}
              onChange={(e) => setDraft({ ...draft, theme: e.target.value as AppSettings["theme"] })}
            >
              <option value="light">{t(lang, "themeLight")}</option>
              <option value="dark">{t(lang, "themeDark")}</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Gemini API Key (Optional)</label>
            <Input
              type="password"
              value={draft.geminiApiKey || ""}
              onChange={(e) => setDraft({ ...draft, geminiApiKey: e.target.value })}
              placeholder="AIzaSy..."
            />
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={handleSave} className="flex-1 bg-[#0078d4] hover:bg-[#006cbd]">{t(lang, "save")}</Button>
            <Button variant="outline" onClick={handleReset}>{t(lang, "reset")}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
