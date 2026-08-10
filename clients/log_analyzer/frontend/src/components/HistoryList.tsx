"use client";

import { Input } from "@/components/ui/input";
import { Search, Code, Trash2 } from "lucide-react";
import { HistoryItem, AppLanguage } from "@/lib/types";
import { t, SortKey, SORT_KEYS, sortLabel, compareBySort } from "@/lib/i18n";

interface HistoryListProps {
  items: HistoryItem[];
  searchTerm: string;
  sortOrder: SortKey;
  language: AppLanguage;
  onSearchChange: (value: string) => void;
  onSortChange: (value: SortKey) => void;
  onItemClick: (item: HistoryItem) => void;
  onDelete: (id: number, e: React.MouseEvent) => void;
}

export function HistoryList({
  items,
  searchTerm,
  sortOrder,
  language,
  onSearchChange,
  onSortChange,
  onItemClick,
  onDelete,
}: HistoryListProps) {
  const filtered = items
    .filter((item) => {
      if (!searchTerm) return true;
      const searchLower = searchTerm.toLowerCase().trim();
      const combined = `event id ${item.eventId} event id: ${item.eventId} ${item.provider} ${item.description} ${item.parseMethod} ${item.eventMetadata?.level || ""}`.toLowerCase();
      return combined.includes(searchLower);
    })
    .sort((a, b) => compareBySort(a, b, sortOrder));

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm">
      <div className="p-4 border-b border-gray-100 dark:border-gray-700 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            placeholder={t(language, "searchPlaceholder")}
            className="pl-9 bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-600 focus-visible:ring-1 focus-visible:ring-[#0078d4]"
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
          <span>{t(language, "sortBy")}</span>
          <select
            className="bg-transparent font-medium text-gray-800 dark:text-gray-200 outline-none cursor-pointer"
            value={sortOrder}
            onChange={(e) => onSortChange(e.target.value as SortKey)}
          >
            {SORT_KEYS.map((key) => (
              <option key={key} value={key}>{sortLabel(language, key)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="divide-y divide-gray-100 dark:divide-gray-700">
        {filtered.length === 0 ? (
          <div className="p-8 text-center text-gray-500 dark:text-gray-400">
            {t(language, "noHistory")}
          </div>
        ) : (
          filtered.map((item) => (
            <div
              key={item.id}
              onClick={() => onItemClick(item)}
              className="p-4 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="font-semibold text-[#0078d4]">
                    {t(language, "eventId")} {item.eventId} - {item.provider}
                  </h4>
                  {item.eventMetadata?.isCritical && (
                    <span className="bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 text-xs px-2 py-0.5 rounded font-medium">
                      {t(language, "critical")}
                    </span>
                  )}
                  {item.eventMetadata?.level && (
                    <span className="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs px-2 py-0.5 rounded">
                      {item.eventMetadata.level}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1 mt-1">
                  <Code className="w-3.5 h-3.5 shrink-0" /> {item.parseMethod || t(language, "parsedViaText")}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2 shrink-0 ml-4">
                <span className="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs px-2 py-0.5 rounded font-medium">
                  {new Date(item.created_at).toISOString().split("T")[0]}
                </span>
                {item.username && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    By: {item.username}
                  </span>
                )}
                {item.feedback_by && (() => {
                  const score = item.feedback_score;
                  const icon = score === 1 ? '👍' : score === -1 ? '👎' : '👍';
                  const label = score === -1 ? `Rejected by: ${item.feedback_by}` : `Verified by: ${item.feedback_by}`;
                  const colorClass = score === -1 ? 'text-red-500 dark:text-red-400' : 'text-blue-500 dark:text-blue-400';
                  return (
                    <span className={`text-xs ${colorClass}`}>
                      {label} {icon}
                    </span>
                  );
                })()}
                <button
                  onClick={(e) => onDelete(item.id, e)}
                  className="text-red-400 hover:text-red-600 focus:outline-none disabled:opacity-30 disabled:cursor-not-allowed"
                  disabled={typeof window !== "undefined" && window.localStorage.getItem("eventiq_token") ? JSON.parse(atob(window.localStorage.getItem("eventiq_token")!.split(".")[1])).role !== "admin" : true}
                  title={typeof window !== "undefined" && window.localStorage.getItem("eventiq_token") && JSON.parse(atob(window.localStorage.getItem("eventiq_token")!.split(".")[1])).role !== "admin" ? t(language, "adminOnly") : ""}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
