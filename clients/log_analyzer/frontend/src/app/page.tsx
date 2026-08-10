"use client";

import { useState, useEffect, useCallback } from "react";
import { LoginForm } from "@/components/LoginForm";
import { Navbar, HistoryDetailDialog } from "@/components/Navbar";
import { AnalyzeDialog } from "@/components/AnalyzeDialog";
import { StatsCards } from "@/components/StatsCards";
import { HistoryList } from "@/components/HistoryList";
import { AppSettings, HistoryItem, StatsData } from "@/lib/types";
import { DEFAULT_SETTINGS, loadSettings, applyTheme } from "@/lib/settings";
import { clearAuthToken, deleteHistoryItem, fetchHistory, fetchStats, getAuthToken } from "@/lib/api";
import { t, SortKey } from "@/lib/i18n";

import { Charts } from "@/components/Charts";
import { CorrelationPanel } from "@/components/CorrelationPanel";

export default function Dashboard() {
  const [hydrated, setHydrated] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [historyList, setHistoryList] = useState<HistoryItem[]>([]);
  const [stats, setStats] = useState<StatsData>({ totalLogs: 0, criticalErrors: 0, avgSearchTimeSec: 0, dailyTrends: [], typeDistribution: [] });
  const [searchTerm, setSearchTerm] = useState("");
  const [sortOrder, setSortOrder] = useState<SortKey>("newest");
  const [selectedItem, setSelectedItem] = useState<HistoryItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const lang = settings.language;

  const refreshData = useCallback(async () => {
    if (!isLoggedIn) return;
    try {
      const [history, statsData] = await Promise.all([
        fetchHistory(settings),
        fetchStats(settings),
      ]);
      setHistoryList(history);
      setStats(statsData);
    } catch (error) {
      console.error("Failed to fetch data:", error);
      if (!getAuthToken()) setIsLoggedIn(false);
    }
  }, [settings, isLoggedIn]);

  useEffect(() => {
    queueMicrotask(() => {
      setSettings(loadSettings());
      if (getAuthToken()) setIsLoggedIn(true);
      setHydrated(true);
    });
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    applyTheme(settings.theme);
    if (isLoggedIn) queueMicrotask(() => void refreshData());
  }, [settings, hydrated, isLoggedIn, refreshData]);

  const handleLogout = () => {
    setIsLoggedIn(false);
    clearAuthToken();
    setHistoryList([]);
    setStats({ totalLogs: 0, criticalErrors: 0, avgSearchTimeSec: 0, dailyTrends: [], typeDistribution: [] });
  };

  const handleDeleteHistory = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(t(lang, "deleteConfirm"))) return;
    try {
      await deleteHistoryItem(settings, id);
      refreshData();
    } catch (error) {
      console.error("Failed to delete history:", error);
    }
  };

  const openHistoryItem = (item: HistoryItem) => {
    setSelectedItem(item);
    setDetailOpen(true);
  };

  if (!hydrated) {
    return <div className="min-h-screen bg-[#f4f7f6] dark:bg-gray-900" />;
  }

  if (!isLoggedIn) {
    return <LoginForm language={lang} settings={settings} onLogin={() => setIsLoggedIn(true)} />;
  }

  return (
    <div className="min-h-screen bg-[#f4f7f6] dark:bg-gray-900">
      <Navbar
        settings={settings}
        onSettingsSave={setSettings}
        onLogout={handleLogout}
      />

      <main className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-gray-100">{t(lang, "analysisHistory")}</h1>
          <AnalyzeDialog settings={settings} onComplete={refreshData} />
        </div>

        {stats.topWeeklyError && (
          <div className="bg-yellow-100 dark:bg-yellow-900/30 border-l-4 border-yellow-500 text-yellow-800 dark:text-yellow-200 p-4 rounded shadow-sm flex items-center justify-between">
            <div>
              <p className="font-bold">{lang === "th" ? "🏆 ปัญหาที่พบบ่อยสุดในสัปดาห์นี้" : "🏆 Top Error of the Week"}</p>
              <p className="text-sm mt-1">
                Event ID: <strong>{stats.topWeeklyError.eventId}</strong> ({stats.topWeeklyError.provider}) 
                - {lang === "th" ? "พบบ่อยถึง" : "Occurred"} <strong className="text-red-600 dark:text-red-400">{stats.topWeeklyError.count}</strong> {lang === "th" ? "ครั้ง" : "times"}
              </p>
            </div>
          </div>
        )}

        <StatsCards stats={stats} language={lang} />
        <Charts stats={stats} language={lang} isDark={settings.theme === 'dark'} />
        <CorrelationPanel settings={settings} language={lang} refreshKey={historyList.length} />

        <HistoryList
          items={historyList}
          searchTerm={searchTerm}
          sortOrder={sortOrder}
          language={lang}
          onSearchChange={setSearchTerm}
          onSortChange={setSortOrder}
          onItemClick={openHistoryItem}
          onDelete={handleDeleteHistory}
        />
      </main>

      <HistoryDetailDialog
        item={selectedItem}
        settings={settings}
        open={detailOpen}
        onOpenChange={(open) => {
          setDetailOpen(open);
          if (!open) refreshData();
        }}
      />
    </div>
  );
}
