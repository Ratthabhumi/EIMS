"use client";

import { FileText, Trash2, Search } from "lucide-react";
import { StatsData, AppLanguage } from "@/lib/types";
import { t } from "@/lib/i18n";

interface StatsCardsProps {
  stats: StatsData;
  language: AppLanguage;
}

export function StatsCards({ stats, language }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-white dark:bg-gray-800 p-5 rounded-lg border border-gray-100 dark:border-gray-700 shadow-sm flex justify-between items-center">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">{t(language, "totalLogs")}</p>
          <h2 className="text-3xl font-bold text-gray-800 dark:text-gray-100">{stats.totalLogs}</h2>
        </div>
        <div className="bg-blue-50 dark:bg-blue-900/30 p-3 rounded-full text-[#0078d4]">
          <FileText className="w-5 h-5" />
        </div>
      </div>
      <div className="bg-white dark:bg-gray-800 p-5 rounded-lg border border-gray-100 dark:border-gray-700 shadow-sm flex justify-between items-center">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">{t(language, "criticalErrors")}</p>
          <h2 className="text-3xl font-bold text-gray-800 dark:text-gray-100">{stats.criticalErrors}</h2>
        </div>
        <div className="bg-red-50 dark:bg-red-900/30 p-3 rounded-full text-red-500">
          <Trash2 className="w-5 h-5" />
        </div>
      </div>
      <div className="bg-white dark:bg-gray-800 p-5 rounded-lg border border-gray-100 dark:border-gray-700 shadow-sm flex justify-between items-center">
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">{t(language, "avgSearchTime")}</p>
          <h2 className="text-3xl font-bold text-gray-800 dark:text-gray-100">
            {stats.avgSearchTimeSec.toFixed(2)}
            <span className="text-lg font-medium text-gray-400 ml-1">{t(language, "sec")}</span>
          </h2>
        </div>
        <div className="bg-green-50 dark:bg-green-900/30 p-3 rounded-full text-green-600">
          <Search className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}
