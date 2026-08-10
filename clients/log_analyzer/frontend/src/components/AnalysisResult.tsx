"use client";

import { Button } from "@/components/ui/button";
import { Download, Search, Link as LinkIcon } from "lucide-react";
import { AnalysisReport, AppLanguage, AppSettings } from "@/lib/types";
import { FollowUpDialog } from "@/components/FollowUpDialog";
import { t } from "@/lib/i18n";
import { sendFeedback } from "@/lib/api";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { useState } from "react";

interface AnalysisResultProps {
  report: AnalysisReport;
  settings: AppSettings;
  language: AppLanguage;
  sourceImage?: File | null;
  sourceText?: string | null;
  onAnalyzeAnother: () => void;
}

function markdownLine(label: string, value?: string) {
  return value ? `- ${label}: ${value}` : "";
}

function buildMarkdown(report: AnalysisReport) {
  const meta = report.eventMetadata;
  const lines = [
    `# EventIQ Analysis Report`,
    "",
    `## Event`,
    markdownLine("Event ID", report.eventId),
    markdownLine("Provider", report.provider),
    markdownLine("Level", meta?.level),
    markdownLine("Log Name", meta?.logName),
    markdownLine("Timestamp", meta?.timestamp),
    markdownLine("Computer", meta?.computer),
    "",
    `## Source`,
    report.description || "No source description.",
    "",
  ].filter((line) => line !== "");

  if (report.solutionSummary) {
    lines.push("## Overview", report.solutionSummary.overview || "No overview.", "");

    if (report.solutionSummary.causes?.length) {
      lines.push("## Possible Causes");
      report.solutionSummary.causes.forEach((cause, idx) => lines.push(`${idx + 1}. ${cause}`));
      lines.push("");
    }

    if (report.solutionSummary.steps?.length) {
      lines.push("## Recommended Steps");
      report.solutionSummary.steps.forEach((step, idx) => lines.push(`${idx + 1}. ${step}`));
      lines.push("");
    }
  } else if (report.aiSummary) {
    lines.push("## Solution Summary", report.aiSummary, "");
  }

  if (report.searchResults?.length) {
    lines.push("## References");
    report.searchResults.forEach((result) => {
      lines.push(`- [${result.title}](${result.link})`);
      if (result.snippet) lines.push(`  ${result.snippet}`);
    });
    lines.push("");
  }

  return `${lines.join("\n")}\n`;
}

function downloadMarkdown(report: AnalysisReport) {
  const markdown = buildMarkdown(report);
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const eventId = report.eventId || "unknown";
  anchor.href = url;
  anchor.download = `eventiq-${eventId}-${Date.now()}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function downloadJSON(report: AnalysisReport) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const eventId = report.eventId || "unknown";
  anchor.href = url;
  anchor.download = `eventiq-${eventId}-${Date.now()}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function exportToPDF(report: AnalysisReport, language: string) {
  const meta = report.eventMetadata;
  const now = new Date().toLocaleString(language === 'th' ? 'th-TH' : 'en-US');

  const causesHtml = (report.solutionSummary?.causes || []).map(
    (c, i) => `<li style="margin-bottom:6px">${i + 1}. ${c}</li>`
  ).join("");
  const stepsHtml = (report.solutionSummary?.steps || []).map(
    (s, i) => `<li style="margin-bottom:8px;padding:8px 12px;background:#f0f9ff;border-left:3px solid #0078d4;border-radius:4px">${i + 1}. ${s}</li>`
  ).join("");
  const refsHtml = (report.searchResults || []).slice(0, 3).map(
    (r) => `<li style="margin-bottom:4px"><a href="${r.link}" style="color:#0078d4">${r.title}</a></li>`
  ).join("");

  const metaHtml = meta ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;font-size:12px">
    ${meta.level ? `<div><span style="color:#888">Level:</span> <strong>${meta.level}</strong></div>` : ""}
    ${meta.logName ? `<div><span style="color:#888">Log:</span> <strong>${meta.logName}</strong></div>` : ""}
    ${meta.timestamp ? `<div><span style="color:#888">Time:</span> <strong>${meta.timestamp}</strong></div>` : ""}
    ${meta.computer ? `<div><span style="color:#888">Computer:</span> <strong>${meta.computer}</strong></div>` : ""}
  </div>` : "";

  const html = `<!DOCTYPE html>
<html lang="${language === 'th' ? 'th' : 'en'}">
<head>
<meta charset="UTF-8">
<title>EventIQ Report — ${report.eventId}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;color:#1a1a1a;background:#fff;padding:40px;max-width:800px;margin:0 auto}
  .hdr{border-bottom:3px solid #0078d4;padding-bottom:16px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:flex-end}
  .brand{font-size:22px;font-weight:700;color:#0078d4}
  .brand small{color:#555;font-size:13px;font-weight:400;display:block;margin-top:2px}
  .evtbox{background:#eff6ff;border-left:4px solid #0078d4;padding:16px;border-radius:6px;margin-bottom:24px}
  .evtid{font-size:17px;font-weight:700;color:#0078d4}
  .badge{display:inline-block;background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:700;margin-left:8px}
  .sec{margin-bottom:22px}
  .sec-title{font-size:13px;font-weight:700;color:#374151;border-bottom:1px solid #e5e7eb;padding-bottom:5px;margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}
  .overview{font-size:14px;color:#374151;line-height:1.7;padding:12px;background:#f9fafb;border-radius:6px}
  ul{padding-left:0;list-style:none}
  .footer{margin-top:40px;border-top:1px solid #e5e7eb;padding-top:10px;font-size:11px;color:#9ca3af;text-align:center}
  @media print{body{padding:20px}}
</style>
</head>
<body>
<div class="hdr">
  <div class="brand">⚡ EventIQ<small>AI-powered Log Analyzer</small></div>
  <div style="font-size:12px;color:#666">Generated: ${now}</div>
</div>
<div class="evtbox">
  <div class="evtid">Event ID: ${report.eventId} — ${report.provider}${meta?.isCritical ? '<span class="badge">CRITICAL</span>' : ""}</div>
  ${report.description ? `<div style="font-size:13px;color:#555;margin-top:4px">${report.description}</div>` : ""}
  ${metaHtml}
</div>
${report.solutionSummary?.overview ? `<div class="sec"><div class="sec-title">${language === "th" ? "ภาพรวมปัญหา" : "Overview"}</div><div class="overview">${report.solutionSummary.overview}</div></div>` : ""}
${causesHtml ? `<div class="sec"><div class="sec-title">${language === "th" ? "สาเหตุที่เป็นไปได้" : "Possible Causes"}</div><ul>${causesHtml}</ul></div>` : ""}
${stepsHtml ? `<div class="sec"><div class="sec-title">${language === "th" ? "วิธีแก้ไข (ทำตามลำดับ)" : "Resolution Steps"}</div><ul>${stepsHtml}</ul></div>` : ""}
${refsHtml ? `<div class="sec"><div class="sec-title">${language === "th" ? "เอกสารอ้างอิง" : "References"}</div><ul>${refsHtml}</ul></div>` : ""}
<div class="footer">EventIQ — AI-powered Log Analyzer | Confidential</div>
</body></html>`;

  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) { alert("Please allow popups to export PDF."); return; }
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => win.print(), 500);
}


export function AnalysisResult({ report, settings, language, sourceImage, sourceText, onAnalyzeAnother }: AnalysisResultProps) {
  const meta = report.eventMetadata;
  const [feedbackSent, setFeedbackSent] = useState<number | null>(null);

  const handleFeedback = async (score: number) => {
    if (!report.historyId) return;
    try {
      const newScore = feedbackSent === score ? 0 : score;
      await sendFeedback(settings, report.historyId, newScore, report.solutionSummary);
      setFeedbackSent(newScore === 0 ? null : newScore);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-4 w-full min-w-0">
      {/* Image preview from upload */}
      {sourceImage && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden">
          <p className="text-xs text-gray-500 dark:text-gray-400 px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
            📎 {language === 'th' ? 'รูปที่ส่งวิเคราะห์:' : 'Submitted image:'} <span className="font-medium">{sourceImage.name || 'pasted-image'}</span>
          </p>
          <img
            src={URL.createObjectURL(sourceImage)}
            alt="Submitted log"
            className="max-h-48 w-full object-contain bg-white dark:bg-gray-950 p-2"
          />
        </div>
      )}
      
      {/* Text preview from upload */}
      {sourceText && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden">
          <p className="text-xs text-gray-500 dark:text-gray-400 px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
            📝 {language === 'th' ? 'ข้อความที่ส่งวิเคราะห์:' : 'Submitted via Text:'}
          </p>
          <div className="bg-white dark:bg-gray-950 p-3 max-h-48 overflow-y-auto">
            <pre className="text-xs text-gray-700 dark:text-gray-300 font-mono whitespace-pre-wrap">{sourceText}</pre>
          </div>
        </div>
      )}

      <div className="bg-blue-50 dark:bg-blue-900/20 border-l-4 border-[#0078d4] p-4 rounded-md break-words w-full">
        <h3 className="font-semibold text-blue-800 dark:text-blue-200 break-words">
          {t(language, "eventId")}: {report.eventId} - {report.provider}
        </h3>
        <p className="text-sm text-blue-600 dark:text-blue-300 mt-1 line-clamp-2 break-words">{report.description}</p>
      </div>

      {meta && (meta.level || meta.logName || meta.timestamp || meta.computer) && (
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 rounded-md grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <h4 className="font-semibold text-gray-800 dark:text-gray-200 col-span-full">{t(language, "metadata")}</h4>
          {meta.level && (
            <div>
              <span className="text-gray-500 dark:text-gray-400">{t(language, "level")}: </span>
              <span className="font-medium text-gray-800 dark:text-gray-200">{meta.level}</span>
            </div>
          )}
          {meta.logName && (
            <div>
              <span className="text-gray-500 dark:text-gray-400">{t(language, "logName")}: </span>
              <span className="font-medium text-gray-800 dark:text-gray-200">{meta.logName}</span>
            </div>
          )}
          {meta.timestamp && (
            <div>
              <span className="text-gray-500 dark:text-gray-400">{t(language, "timestamp")}: </span>
              <span className="font-medium text-gray-800 dark:text-gray-200">{meta.timestamp}</span>
            </div>
          )}
          {meta.computer && (
            <div>
              <span className="text-gray-500 dark:text-gray-400">{t(language, "computer")}: </span>
              <span className="font-medium text-gray-800 dark:text-gray-200">{meta.computer}</span>
            </div>
          )}
        </div>
      )}

      {report.solutionSummary ? (
        <div className="space-y-4 w-full">
          <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 rounded-md w-full">
            <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{t(language, "overview")}</h4>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{report.solutionSummary.overview}</p>
          </div>

          {report.solutionSummary.causes?.length > 0 && (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800 p-4 rounded-md w-full">
              <h4 className="font-semibold text-amber-900 dark:text-amber-200 mb-2">{t(language, "causes")}</h4>
              <ol className="list-decimal list-inside space-y-1.5 text-sm text-amber-900/90 dark:text-amber-100">
                {report.solutionSummary.causes.map((cause, idx) => (
                  <li key={idx} className="leading-relaxed">{cause}</li>
                ))}
              </ol>
            </div>
          )}

          {report.solutionSummary.steps?.length > 0 && (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-100 dark:border-green-800 p-4 rounded-md w-full">
              <h4 className="font-semibold text-green-900 dark:text-green-200 mb-2">{t(language, "steps")}</h4>
              <ol className="list-decimal list-inside space-y-2 text-sm text-green-900/90 dark:text-green-100">
                {report.solutionSummary.steps.map((step, idx) => (
                  <li key={idx} className="leading-relaxed">{step}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      ) : report.aiSummary ? (
        <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-4 rounded-md w-full">
          <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{t(language, "solutionSummary")}</h4>
          <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{report.aiSummary}</p>
        </div>
      ) : null}

      <div className="w-full min-w-0">
        <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-[#0078d4]" /> {t(language, "references")}
        </h4>
        <div className="space-y-3 w-full min-w-0">
          {report.searchResults?.map((result, idx) => (
            <a
              key={idx}
              href={result.link}
              target="_blank"
              rel="noreferrer"
              className="block p-3 rounded-md border border-gray-100 dark:border-gray-700 hover:border-[#0078d4] hover:bg-blue-50/50 dark:hover:bg-blue-900/20 transition-colors w-full min-w-0"
            >
              <div className="flex items-start gap-2 w-full min-w-0">
                <LinkIcon className="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-blue-700 dark:text-blue-300 truncate">{result.title}</p>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${
                        result.sourceType === "official"
                          ? "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                          : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                      }`}
                    >
                      {result.sourceType === "official" ? t(language, "official") : t(language, "community")}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">{result.link}</p>
                  {result.snippet && (
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-2 line-clamp-2">{result.snippet}</p>
                  )}
                </div>
              </div>
            </a>
          ))}
        </div>
      </div>

      {report.solutionSummary && (
        <FollowUpDialog
          settings={settings}
          report={{
            eventId: report.eventId,
            provider: report.provider,
            solutionSummary: report.solutionSummary,
            searchResults: report.searchResults?.map((result) => ({ title: result.title, link: result.link })) || [],
          }}
        />
      )}

      <div className="flex flex-col gap-2 mt-4 print:hidden">
        {report.historyId && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
                {language === 'th' ? "คำตอบนี้ช่วยได้หรือไม่?" : "Was this helpful?"}
              </span>
              <div className="flex items-center gap-1 border border-gray-200 dark:border-gray-700 rounded-md p-1 bg-gray-50 dark:bg-gray-800">
                <Button
                  variant={feedbackSent === 1 ? "default" : "ghost"}
                  size="sm"
                  className={`h-8 px-2 ${feedbackSent === 1 ? "bg-green-600 hover:bg-green-700" : ""}`}
                  onClick={() => handleFeedback(1)}
                  title="Good solution (adds to knowledge base)"
                >
                  <ThumbsUp className={`w-4 h-4 ${feedbackSent === 1 ? "text-white" : "text-green-600 dark:text-green-400"}`} />
                  {feedbackSent === 1 && <span className="ml-1 text-xs">Verified</span>}
                </Button>
                <Button
                  variant={feedbackSent === -1 ? "destructive" : "ghost"}
                  size="sm"
                  className={`h-8 px-2 ${feedbackSent === -1 ? "bg-red-600 hover:bg-red-700" : ""}`}
                  onClick={() => handleFeedback(-1)}
                  title="Bad solution"
                >
                  <ThumbsDown className={`w-4 h-4 ${feedbackSent === -1 ? "text-white" : "text-red-600 dark:text-red-400"}`} />
                  {feedbackSent === -1 && <span className="ml-1 text-xs">Not Verified</span>}
                </Button>
              </div>
            </div>
            {feedbackSent !== null && (
              <p className={`text-sm ${feedbackSent === 1 ? 'text-green-600' : 'text-amber-600'}`}>
                {language === 'th' ? 'บันทึกความคิดเห็นแล้ว ขอบคุณครับ!' : 'Feedback recorded. Thank you!'}
                {feedbackSent === -1 && (
                  <span className="block text-xs mt-1">
                    {language === 'th' ? '(คำตอบนี้จะไม่ถูกบันทึกเพื่อใช้ในอนาคต)' : '(This solution will not be saved for future use)'}
                  </span>
                )}
              </p>
            )}
          </div>
        )}
        
        <div className="flex flex-wrap gap-2 w-full mt-2">
          <Button variant="outline" className="flex-1 min-w-[120px]" onClick={() => downloadMarkdown(report)}>
            <Download className="w-4 h-4 mr-2" />
            Export MD
          </Button>
          <Button variant="outline" className="flex-1 min-w-[120px]" onClick={() => downloadJSON(report)}>
            <Download className="w-4 h-4 mr-2" />
            Export JSON
          </Button>
          <Button variant="outline" className="flex-1 min-w-[120px]" onClick={() => exportToPDF(report, language)}>
            <Download className="w-4 h-4 mr-2" />
            Export PDF
          </Button>
          <Button variant="outline" className="w-full mt-2" onClick={onAnalyzeAnother}>
            {t(language, "analyzeAnother")}
          </Button>
        </div>
      </div>
    </div>
  );
}
