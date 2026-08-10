"use client";

import { FileText } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { SettingsDialog } from "@/components/SettingsDialog";
import { AnalysisResult } from "@/components/AnalysisResult";
import { AppSettings, HistoryItem } from "@/lib/types";
import { t } from "@/lib/i18n";

interface NavbarProps {
  settings: AppSettings;
  onSettingsSave: (settings: AppSettings) => void;
  onLogout: () => void;
}

import { getAuthUser } from "@/lib/api";

export function Navbar({ settings, onSettingsSave, onLogout }: NavbarProps) {
  const lang = settings.language;
  const authUser = getAuthUser();
  const username = authUser?.username || "Guest";

  return (
    <nav className="bg-[#0078d4] text-white px-4 sm:px-6 py-3 flex justify-between items-center">
      <div className="flex items-center gap-2 font-semibold text-lg">
        <FileText className="w-5 h-5" />
        EventIQ
      </div>
      <div className="flex items-center gap-4 sm:gap-6 text-sm">
        <span className="font-medium hidden sm:inline"><a href="/"> {t(lang, "dashboard")}</a></span>
        {authUser?.role === "admin" && (
          <span className="font-medium hidden sm:inline text-yellow-300">
            <a href="/admin">Admin Panel 🛡️</a>
          </span>
        )}
        <SettingsDialog settings={settings} onSave={onSettingsSave} />
        <div className="flex items-center gap-2">
          <img
            src={`https://ui-avatars.com/api/?name=${username}&background=random&color=fff`}
            alt={username}
            className="w-6 h-6 rounded-full"
          />
          <span className="hidden sm:inline">{username}</span>
        </div>
        <span className="cursor-pointer hover:text-blue-200" onClick={onLogout}>{t(lang, "logout")}</span>
      </div>
    </nav>
  );
}

interface HistoryDetailDialogProps {
  item: HistoryItem | null;
  settings: AppSettings;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function HistoryDetailDialog({ item, settings, open, onOpenChange }: HistoryDetailDialogProps) {
  if (!item) return null;

  const report = {
    eventId: item.eventId,
    provider: item.provider,
    description: item.parseMethod || item.description,
    eventMetadata: item.eventMetadata,
    aiSummary: item.aiSummary,
    solutionSummary: item.solutionSummary,
    searchResults: item.searchResults,
    historyId: item.id,
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl bg-white dark:bg-gray-800 overflow-hidden max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-gray-800 dark:text-gray-100">
            {t(settings.language, "analysisResult")}
          </DialogTitle>
        </DialogHeader>
        <AnalysisResult
          report={report}
          settings={settings}
          language={settings.language}
          onAnalyzeAnother={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
