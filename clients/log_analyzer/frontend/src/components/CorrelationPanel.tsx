"use client";

import { useState, useEffect } from "react";
import { AppSettings } from "@/lib/types";
import { apiBase, getAuthToken } from "@/lib/api";
import { GitBranch, RefreshCw, AlertTriangle, Clock, Repeat } from "lucide-react";
import { Button } from "@/components/ui/button";

interface CorrelationData {
  topRepeated: { eventId: string; provider: string; count: number; label: string }[];
  timeCorrelated: { eventIds: string[]; count: number; label: string }[];
  criticalClusters: { date: string; eventIds: string[]; count: number; label: string }[];
  hasInsights: boolean;
}

interface CorrelationPanelProps {
  settings: AppSettings;
  language: string;
  refreshKey?: number;
}

export function CorrelationPanel({ settings, language, refreshKey }: CorrelationPanelProps) {
  const [data, setData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchCorrelations = async () => {
    setLoading(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`${apiBase(settings)}/api/v1/stats/correlations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCorrelations();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  if (!data || !data.hasInsights) return null;

  const th = language === "th";

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-purple-600 dark:text-purple-400" />
          <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm">
            {th ? "🔗 Log Correlation — Pattern ที่น่าสนใจ" : "🔗 Log Correlation — Detected Patterns"}
          </h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={fetchCorrelations}
          disabled={loading}
          className="h-7 px-2 text-gray-400"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Repeated Events */}
        {data.topRepeated.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-orange-600 dark:text-orange-400 flex items-center gap-1">
              <Repeat className="w-3 h-3" />
              {th ? "Event ที่เกิดซ้ำ" : "Repeated Events"}
            </p>
            {data.topRepeated.map((item, i) => (
              <div
                key={i}
                className="bg-orange-50 dark:bg-orange-900/20 border border-orange-100 dark:border-orange-800/40 rounded-md px-3 py-2"
              >
                <p className="text-xs font-bold text-orange-700 dark:text-orange-300">
                  Event {item.eventId}
                  <span className="ml-1.5 bg-orange-200 dark:bg-orange-800 text-orange-800 dark:text-orange-200 rounded px-1 py-0.5 text-[10px]">
                    ×{item.count}
                  </span>
                </p>
                <p className="text-[11px] text-orange-600/80 dark:text-orange-400/80 truncate">{item.provider}</p>
              </div>
            ))}
          </div>
        )}

        {/* Time Correlated */}
        {data.timeCorrelated.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {th ? "เกิดพร้อมกัน (ภายใน 5 นาที)" : "Co-occurring (within 5 min)"}
            </p>
            {data.timeCorrelated.map((item, i) => (
              <div
                key={i}
                className="bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800/40 rounded-md px-3 py-2"
              >
                <p className="text-xs font-bold text-blue-700 dark:text-blue-300">
                  {item.eventIds.join(" ↔ ")}
                  <span className="ml-1.5 bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200 rounded px-1 py-0.5 text-[10px]">
                    ×{item.count}
                  </span>
                </p>
                <p className="text-[11px] text-blue-500/80 truncate">{item.label}</p>
              </div>
            ))}
          </div>
        )}

        {/* Critical Clusters */}
        {data.criticalClusters.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-red-600 dark:text-red-400 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              {th ? "Critical Event กระจุกตัว" : "Critical Clusters"}
            </p>
            {data.criticalClusters.map((item, i) => (
              <div
                key={i}
                className="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800/40 rounded-md px-3 py-2"
              >
                <p className="text-xs font-bold text-red-700 dark:text-red-300">
                  {item.date}
                  <span className="ml-1.5 bg-red-200 dark:bg-red-800 text-red-800 dark:text-red-200 rounded px-1 py-0.5 text-[10px]">
                    {item.count} events
                  </span>
                </p>
                <p className="text-[11px] text-red-500/80 truncate">{item.eventIds.join(", ")}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
