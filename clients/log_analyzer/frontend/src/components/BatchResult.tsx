"use client";

import { AnalysisReport, AppLanguage } from "@/lib/types";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BatchResultProps {
  results: { filename: string; report: AnalysisReport | null; error?: string }[];
  language: AppLanguage;
  onClose: () => void;
}

export function BatchResult({ results, language, onClose }: BatchResultProps) {
  const successCount = results.filter((r) => r.report).length;
  const criticalCount = results.filter((r) => r.report?.eventMetadata?.isCritical).length;

  const exportBatchCSV = () => {
    const headers = ["Filename", "Event ID", "Provider", "Level", "Is Critical", "Overview"];
    const rows = results.map((r) => [
      r.filename,
      r.report?.eventId ?? "Error",
      r.report?.provider ?? "",
      r.report?.eventMetadata?.level ?? "",
      r.report?.eventMetadata?.isCritical ? "YES" : "NO",
      (r.report?.solutionSummary?.overview ?? r.error ?? "").replace(/,/g, ";"),
    ]);
    const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `eventiq-batch-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 w-full">
      {/* Summary banner */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
        <h3 className="font-bold text-blue-800 dark:text-blue-200 text-base mb-1">
          📦 {language === "th" ? "ผลลัพธ์ Batch Analysis" : "Batch Analysis Results"}
        </h3>
        <div className="flex gap-4 text-sm mt-2">
          <span className="text-green-600 dark:text-green-400 font-medium">
            ✅ {language === "th" ? "สำเร็จ" : "Success"}: {successCount}/{results.length}
          </span>
          {criticalCount > 0 && (
            <span className="text-red-600 dark:text-red-400 font-medium">
              🚨 Critical: {criticalCount}
            </span>
          )}
          <span className="text-gray-500 dark:text-gray-400">
            {language === "th" ? "ล้มเหลว" : "Failed"}: {results.length - successCount}
          </span>
        </div>
      </div>

      {/* Results table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
              <th className="text-left px-3 py-2 font-semibold text-gray-600 dark:text-gray-300">
                {language === "th" ? "ไฟล์" : "File"}
              </th>
              <th className="text-left px-3 py-2 font-semibold text-gray-600 dark:text-gray-300">Event ID</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-600 dark:text-gray-300">Provider</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-600 dark:text-gray-300">
                {language === "th" ? "ระดับ" : "Level"}
              </th>
              <th className="text-left px-3 py-2 font-semibold text-gray-600 dark:text-gray-300">
                {language === "th" ? "สรุป" : "Overview"}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {results.map((r, idx) => (
              <tr
                key={idx}
                className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${
                  r.report?.eventMetadata?.isCritical
                    ? "bg-red-50/30 dark:bg-red-900/10"
                    : ""
                }`}
              >
                <td className="px-3 py-2 font-medium text-gray-700 dark:text-gray-300 max-w-[140px] truncate" title={r.filename}>
                  {r.filename}
                </td>
                <td className="px-3 py-2">
                  {r.report ? (
                    <span className="font-semibold text-[#0078d4]">{r.report.eventId}</span>
                  ) : (
                    <span className="text-red-500 text-xs">Error</span>
                  )}
                </td>
                <td className="px-3 py-2 text-gray-600 dark:text-gray-400 max-w-[130px] truncate" title={r.report?.provider}>
                  {r.report?.provider ?? "—"}
                </td>
                <td className="px-3 py-2">
                  {r.report?.eventMetadata?.isCritical ? (
                    <span className="bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 text-xs px-1.5 py-0.5 rounded font-medium">
                      {r.report.eventMetadata.level || "Critical"}
                    </span>
                  ) : (
                    <span className="text-gray-500 dark:text-gray-400 text-xs">
                      {r.report?.eventMetadata?.level || "—"}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-gray-600 dark:text-gray-400 text-xs max-w-[200px]">
                  {r.error ? (
                    <span className="text-red-500">{r.error.slice(0, 80)}</span>
                  ) : (
                    <span className="line-clamp-2">{r.report?.solutionSummary?.overview || r.report?.aiSummary?.slice(0, 100) || "—"}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <Button variant="outline" size="sm" onClick={exportBatchCSV} className="flex items-center gap-1.5">
          <Download className="w-3.5 h-3.5" />
          {language === "th" ? "ส่งออก CSV" : "Export CSV"}
        </Button>
        <Button variant="outline" size="sm" onClick={onClose} className="flex-1">
          {language === "th" ? "วิเคราะห์ใหม่" : "Analyze Another"}
        </Button>
      </div>
    </div>
  );
}
