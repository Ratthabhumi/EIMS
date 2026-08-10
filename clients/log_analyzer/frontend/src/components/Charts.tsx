"use client";

import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from "recharts";
import { StatsData } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface ChartsProps {
  stats: StatsData;
  language: string;
  isDark?: boolean;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ef4444'];
const DARK_COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa', '#22d3ee', '#f87171'];

function useDarkMode(): boolean {
  if (typeof window === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

export function Charts({ stats, language, isDark: isDarkProp }: ChartsProps) {
  // Detect dark mode from DOM if not explicitly passed
  const isDark = isDarkProp ?? useDarkMode();

  const palette = isDark ? DARK_COLORS : COLORS;

  // Recharts theme tokens
  const axisColor = isDark ? "#9ca3af" : "#6b7280";
  const tooltipStyle: React.CSSProperties = {
    backgroundColor: isDark ? "#1f2937" : "#ffffff",
    border: "none",
    borderRadius: "8px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
    color: isDark ? "#f9fafb" : "#111827",
  };
  const legendStyle: React.CSSProperties = {
    color: isDark ? "#d1d5db" : "#374151",
    fontSize: "12px",
  };

  const sortedTrends = useMemo(() => {
    if (!stats.dailyTrends) return [];
    return [...stats.dailyTrends].sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
    );
  }, [stats.dailyTrends]);

  if (!stats.dailyTrends || stats.dailyTrends.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
      {/* Bar Chart — Daily Trends */}
      <Card className="dark:bg-gray-800 dark:border-gray-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {language === "th" ? "แนวโน้มรายสัปดาห์ (Daily Trends)" : "Weekly Trends (Last 7 Days)"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[250px] w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sortedTrends}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: axisColor, fontSize: 11 }}
                  axisLine={{ stroke: axisColor }}
                  tickLine={false}
                  tickFormatter={(str) => {
                    const date = new Date(str);
                    return `${date.getMonth() + 1}/${date.getDate()}`;
                  }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: axisColor, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: isDark ? "#f9fafb" : "#111827", fontWeight: 600 }}
                  itemStyle={{ color: palette[0] }}
                  cursor={{ fill: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)" }}
                  labelFormatter={(str) =>
                    new Date(str).toLocaleDateString(language === "th" ? "th-TH" : "en-US")
                  }
                />
                <Bar dataKey="count" fill={palette[0]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Donut Chart — Provider Distribution */}
      <Card className="dark:bg-gray-800 dark:border-gray-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-500 dark:text-gray-400">
            {language === "th" ? "สัดส่วน Error ตามประเภท (Provider)" : "Error Distribution (Provider)"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[250px] w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={stats.typeDistribution}
                  cx="50%"
                  cy="45%"
                  innerRadius={55}
                  outerRadius={78}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {stats.typeDistribution.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={palette[index % palette.length]}
                      stroke={isDark ? "#1f2937" : "#ffffff"}
                      strokeWidth={2}
                    />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: isDark ? "#f9fafb" : "#111827" }} />
                <Legend
                  wrapperStyle={legendStyle}
                  iconType="circle"
                  iconSize={8}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
