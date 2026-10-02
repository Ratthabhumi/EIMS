import React from 'react';
import { apiUrl } from '../lib/api';
import {
  AlertCircle,
  Info,
  FileText,
  CheckCircle2,
  Link as LinkIcon,
  MessageSquare,
  Download,
  Code,
  FileImage,
  Monitor
} from "lucide-react";

interface AnalysisResultDetailProps {
  result: any;
  language?: string;
  onDownloadMD?: () => void;
  onDownloadJSON?: () => void;
}

export default function AnalysisResultDetail({ result, language, onDownloadMD, onDownloadJSON }: AnalysisResultDetailProps) {
  const [feedback, setFeedback] = React.useState<number>(result?.feedback_score || 0);
  const [question, setQuestion] = React.useState<string>("");
  const [answer, setAnswer] = React.useState<string>("");
  const [asking, setAsking] = React.useState<boolean>(false);
  const [askError, setAskError] = React.useState<string>("");

  if (!result) return null;

  // Resolve in order: historyId -> bundleId (alias) -> id (history rows).
  const historyId: number | undefined =
    typeof result.historyId === "number"
      ? result.historyId
      : typeof result.bundleId === "number"
        ? result.bundleId
        : typeof result.id === "number"
          ? result.id
          : undefined;

  const submitFollowUp = async () => {
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    setAskError("");
    setAnswer("");
    try {
      const res = await fetch(apiUrl("/api/v1/analyze/followup"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          eventId,
          provider,
          language: language || "th",
          historyId,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `Follow-up failed (${res.status})`);
      }
      const data = await res.json();
      setAnswer(data.answer || "");
    } catch (e: any) {
      setAskError(e?.message || "Follow-up request failed.");
    } finally {
      setAsking(false);
    }
  };

  // Extract variables
  const eventId = result.eventId || "Unknown";
  const provider = result.provider || "Unknown";
  const parseMethod = result.parseMethod || "Text Parsing";
  const numEvents = 1;

  const summary = result.solutionSummary?.overview || result.summary || result.aiSummary || result.root_cause || "No summary available.";
  const steps = result.solutionSummary?.steps || (result.solution ? [result.solution] : []);
  const causes = result.solutionSummary?.causes || [];

  const metadata = result.eventMetadata || {};
  const searchResults = result.searchResults || [];

  // Source-aware diagnostic identity (vendor logs show Product + Diagnostic
  // Code instead of fake Event ID semantics).
  const diagCode = metadata.diagnosticCode || "";
  const product = metadata.product || "";
  const hasVendorDiag = !!diagCode;
  const solEvidence: string[] = result.solutionSummary?.evidence || [];
  const solConfidence: string = result.solutionSummary?.confidence || "";
  const solUnknowns: string[] = result.solutionSummary?.limitations || [];
  const solNextEvidence: string[] = result.solutionSummary?.nextEvidence || [];
  const incident = result.solutionSummary?.incident || null;
  const evidenceItems: any[] = result.solutionSummary?.evidenceItems || [];
  const bundleFiles: any[] = result.files || [];
  const correlationConfidence: string = result.correlationConfidence || "";
  const correlationReasons: string[] = result.correlationReasons || [];
  const correlatedSources: string[] = result.correlatedSources || [];
  const isBundle = bundleFiles.length > 0 || !!correlationConfidence;

  // Detect language: use language prop if explicitly provided, else detect from text (Thai character check)
  const isThaiText = (text: string) => /[\u0E00-\u0E7F]/.test(text);
  const detectedEn = !isThaiText(summary) && (!steps.length || !isThaiText(steps.join(" ")));
  const isEn = language ? language === "en" : detectedEn;

  const isIncident = String(eventId).toUpperCase().startsWith("AINC-");
  const isCatalog = result.isCatalog === true;
  const displayTitle = isIncident
    ? "Suspicious Authentication Activity"
    : (result.solutionSummary?.title || (isCatalog ? `Event ${eventId}` : `Event ID: ${eventId}`));
  const displayProvider = isIncident
    ? "Security / Authentication"
    : provider;

  return (
    <div className="flex flex-col gap-6 animate-fade-in w-full">

      {/* Header Box */}
      <div className={`bg-eims-surface border-l-4 ${isIncident ? "border-l-purple-500" : isCatalog ? "border-l-sky-500" : "border-l-teal-500"} border border-eims-border rounded-lg p-4 shadow-sm relative overflow-hidden`}>
        <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
          <AlertCircle size={100} />
        </div>
        <h3 className="text-lg font-semibold text-eims-text flex flex-wrap items-center gap-2">
          {isIncident ? (
            <>
              <span className="text-eims-info dark:text-sky-400 font-bold">{displayTitle}</span>
              <span className="text-eims-text-secondary font-normal text-sm ml-1">({displayProvider})</span>
            </>
          ) : isCatalog ? (
            <>
              <span className="text-eims-info dark:text-sky-400 font-bold">{displayTitle}</span>
              <span className="text-eims-text-secondary font-normal text-sm ml-1">({displayProvider} · Event {eventId})</span>
            </>
          ) : hasVendorDiag ? (
            <>
              <span className="text-eims-info dark:text-sky-400 font-bold">{product || provider}</span>
              <span className="text-eims-text-secondary font-normal text-sm ml-1">· Diagnostic {diagCode}</span>
              <span className="text-eims-text-secondary font-normal text-sm ml-2">{isEn ? "Number of events:" : "จำนวนเหตุการณ์:"} {numEvents}</span>
            </>
          ) : (
            <>
              Event ID: <span className="text-eims-info dark:text-sky-400 font-bold">{eventId}</span> - {provider}
              <span className="text-eims-text-secondary font-normal text-sm ml-2">{isEn ? "Number of events:" : "จำนวนเหตุการณ์:"} {numEvents}</span>
            </>
          )}
        </h3>
        <div className="flex flex-wrap items-center gap-2 mt-2 text-sm">
          {isIncident ? (
            <>
              <span className="bg-purple-500/10 border border-purple-500/30 text-purple-600 dark:text-purple-400 text-xs font-semibold px-2.5 py-0.5 rounded uppercase tracking-wide">
                SYNTHETIC / AI DEMO DATA
              </span>
              <span className="text-xs text-eims-text-secondary">Incident {eventId}</span>
            </>
          ) : isCatalog ? (
            <p className="text-eims-info dark:text-sky-400 text-xs sm:text-sm flex items-center gap-2">
              <FileText size={14} />
              Operational Event Catalog Knowledge Reference (Static)
            </p>
          ) : (
            <p className="text-eims-info dark:text-sky-400 text-sm flex items-center gap-2">
              {parseMethod.includes("OCR") ? <FileImage size={14} /> : <FileText size={14} />}
              (Extracted via {parseMethod})
            </p>
          )}
        </div>
      </div>

      {/* Event Info and Summary in a 2-column Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Event Info Grid Box */}
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-4 flex items-center gap-2">
            <Info className="w-5 h-5 text-eims-text-secondary" /> {isEn ? "Event Details" : "ข้อมูล Event"}
          </h4>
          <div className="flex flex-col gap-3 text-sm">
          <div>
            <span className="text-eims-text-muted">{isEn ? "Level:" : "ระดับ (Level):"}</span>
            <span className="ml-2 font-medium text-eims-text">{metadata.level || "Error"}</span>
          </div>
          <div>
            <span className="text-eims-text-muted">{isEn ? "Log Name:" : "Log Name:"}</span>
            <span className="ml-2 font-medium text-eims-text">{metadata.logName || "Application"}</span>
          </div>
          <div>
            <span className="text-eims-text-muted">{isEn ? "Time:" : "เวลา (Time):"}</span>
            <span className="ml-2 font-medium text-eims-text">{metadata.timestamp || "N/A"}</span>
          </div>
          <div className="flex items-center">
            <span className="text-eims-text-muted">{isEn ? "Computer:" : "คอมพิวเตอร์:"}</span>
            <span className="ml-2 font-medium text-eims-text flex items-center gap-1">
              <Monitor size={14} className="text-eims-text-secondary"/>
              {metadata.computer || "Localhost"}
            </span>
          </div>
          {metadata.faultingApp && (
            <div className="col-span-1 md:col-span-2">
               <span className="text-eims-text-muted">Faulting App:</span>
               <span className="ml-2 font-medium text-red-400">{metadata.faultingApp}</span>
            </div>
          )}
        </div>
      </div>

        {/* Summary Box */}
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm flex flex-col">
          <h4 className="text-md font-semibold text-eims-text mb-3 flex items-center gap-2">
            <FileText className="w-5 h-5 text-amber-600 dark:text-amber-400" /> {isEn ? "Problem Summary" : "สรุปปัญหา"}
          </h4>
        <div className="text-eims-text-secondary leading-relaxed text-sm">
          {summary}
        </div>
        {causes.length > 0 && (
          <div className="mt-3 pl-4 border-l-2 border-red-500/30">
            <p className="text-sm text-red-500 mb-1 font-medium">{isEn ? (hasVendorDiag ? "Likely Causes / Assessment:" : "Root Causes:") : "สาเหตุที่เป็นไปได้:"}</p>
            <ul className="list-disc pl-4 text-sm text-eims-text-secondary space-y-1">
              {causes.map((cause: string, idx: number) => (
                <li key={idx}>{cause}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      </div>

      {/* Resolution Steps */}
      <div className="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/50 rounded-lg p-4 shadow-sm">
        <h4 className="text-md font-semibold text-emerald-700 dark:text-emerald-400 mb-4 flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5" /> {isEn ? "Resolution Steps" : "วิธีแก้ไข (ทำตามลำดับ)"}
        </h4>
        <div className="space-y-3">
          {steps.length > 0 ? steps.map((step: string, idx: number) => (
            <div key={idx} className="flex gap-3 text-sm">
              <span className="text-emerald-600 dark:text-emerald-500 font-bold">{idx + 1}.</span>
              <span className="text-emerald-800 dark:text-emerald-100/70 leading-relaxed">{step}</span>
            </div>
          )) : (
            <div className="text-sm text-emerald-600/70 dark:text-emerald-100/50">{isEn ? "No specific steps provided." : "ไม่มีขั้นตอนแนะนำเฉพาะเจาะจง"}</div>
          )}
        </div>
      </div>

      {/* Observed Evidence */}
      {solEvidence.length > 0 && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-3">
            {isEn ? "Observed Evidence" : "หลักฐานที่พบ"}
          </h4>
          <ul className="list-disc pl-4 text-sm text-eims-text-secondary space-y-1">
            {solEvidence.map((e: string, idx: number) => (
              <li key={idx} className="font-mono text-xs">{e}</li>
            ))}
          </ul>
          {solConfidence && (
            <p className="text-xs text-eims-text-muted mt-2">
              {isEn ? "Confidence: " : "ความมั่นใจ: "}
              <span className="font-semibold text-eims-text capitalize">{solConfidence}</span>
            </p>
          )}
        </div>
      )}

      {/* What Is Still Unknown */}
      {solUnknowns.length > 0 && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-3">
            {isEn ? "What Is Still Unknown" : "สิ่งที่ยังไม่ทราบ"}
          </h4>
          <ul className="list-disc pl-4 text-sm text-eims-text-secondary space-y-1">
            {solUnknowns.map((u: string, idx: number) => (
              <li key={idx}>{u}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Next Evidence to Collect */}
      {solNextEvidence.length > 0 && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-3">
            {isEn ? "Next Evidence to Collect" : "หลักฐานที่ควรเก็บเพิ่ม"}
          </h4>
          <ul className="list-disc pl-4 text-sm text-eims-text-secondary space-y-1">
            {solNextEvidence.map((n: string, idx: number) => (
              <li key={idx}>{n}</li>
            ))}
          </ul>
        </div>
      )}

      {/* References */}
      {searchResults.length > 0 && (
        <div>
          <h4 className="text-md font-semibold text-blue-600 dark:text-blue-400 mb-3 flex items-center gap-2">
            <LinkIcon className="w-4 h-4" /> {isEn ? "References Found:" : "ลิงก์อ้างอิงที่พบ:"}
          </h4>
          <div className="space-y-3">
            {searchResults.map((ref: any, idx: number) => (
              <a
                key={idx}
                href={ref.link}
                target="_blank"
                rel="noopener noreferrer"
                className="block bg-eims-surface border border-eims-border hover:border-blue-500/50 rounded-lg p-4 transition-all group"
              >
                <div className="flex justify-between items-start mb-1">
                  <h5 className="text-blue-600 dark:text-blue-400 font-medium group-hover:underline text-sm">{ref.title}</h5>
                  <span className="text-[10px] bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-500/10 dark:text-blue-400 px-2 py-0.5 rounded border dark:border-blue-500/20 whitespace-nowrap ml-2">
                    {ref.sourceType === "official" ? "Official" : "Community"}
                  </span>
                </div>
                <p className="text-xs text-eims-text-muted truncate mb-2">{ref.link}</p>
                <p className="text-xs text-eims-text-secondary line-clamp-2">{ref.snippet}</p>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Feedback Rating Section */}
      {!isCatalog && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm flex items-center justify-between">
          <div>
            <h4 className="text-xs font-semibold text-eims-text uppercase tracking-wider">
              {isEn ? "Was this solution helpful?" : "วิธีแก้ไขนี้ช่วยแก้ปัญหาได้ตรงจุดหรือไม่?"}
            </h4>
            <p className="text-[11px] text-eims-text-secondary mt-0.5">
              {isEn ? "Your feedback improves the Vector RAG Knowledge Base accuracy." : "คะแนนของคุณจะช่วยให้ AI Vector RAG จดจำและแม่นยำขึ้นในอนาคต"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                if (result.id && typeof result.id === "number") {
                  try {
                    await fetch(apiUrl(`/api/v1/history/${result.id}/feedback?score=1`), { method: "POST" });
                  } catch (e) {}
                }
                setFeedback(1);
              }}
              className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-all ${
                feedback === 1
                  ? "bg-teal-500/20 border-teal-500 text-teal-400 font-bold"
                  : "border-eims-border hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text"
              }`}
            >
              👍 {isEn ? "Helpful" : "ใช้ได้ผล"}
            </button>
            <button
              onClick={async () => {
                if (result.id && typeof result.id === "number") {
                  try {
                    await fetch(apiUrl(`/api/v1/history/${result.id}/feedback?score=-1`), { method: "POST" });
                  } catch (e) {}
                }
                setFeedback(-1);
              }}
              className={`px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition-all ${
                feedback === -1
                  ? "bg-rose-500/20 border-rose-500 text-rose-400 font-bold"
                  : "border-eims-border hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text"
              }`}
            >
              👎 {isEn ? "Not Helpful" : "ไม่ได้ผล"}
            </button>
          </div>
        </div>
      )}

      {/* Bundle correlation */}
      {isBundle && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-3">
            {isEn ? "Correlated Sources" : "แหล่งหลักฐานที่เชื่อมโยง"}
            {correlationConfidence && (
              <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded border border-eims-border text-eims-text-secondary capitalize">
                {correlationConfidence}
              </span>
            )}
          </h4>
          {bundleFiles.length > 0 && (
            <ul className="text-sm text-eims-text-secondary space-y-1 mb-2">
              {bundleFiles.map((f: any, idx: number) => (
                <li key={idx} className="font-mono text-xs">
                  {f.filename}
                  {f.diagnosticCode ? ` · ${f.diagnosticCode}` : ""}
                  {f.sha256 ? ` · sha256:${String(f.sha256).slice(0, 12)}…` : ""}
                </li>
              ))}
            </ul>
          )}
          {correlatedSources.length > 0 && (
            <p className="text-xs text-eims-text-secondary mb-2">
              {isEn ? "Correlated: " : "ไฟล์ที่เชื่อมโยง: "}{correlatedSources.join(", ")}
            </p>
          )}
          {correlationReasons.length > 0 && (
            <ul className="list-disc pl-4 text-sm text-eims-text-secondary space-y-1">
              {correlationReasons.map((r: string, idx: number) => (
                <li key={idx}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Structured incident */}
      {incident && (incident.firstMeaningfulFailure || incident.terminalFailure || (incident.observedPaths || []).length > 0) && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-3">
            {isEn ? "Failure Sequence (Observed)" : "ลำดับความล้มเหลว (ที่พบจริง)"}
          </h4>
          <div className="text-sm text-eims-text-secondary space-y-2">
            {incident.firstMeaningfulFailure && (
              <p><span className="font-medium text-eims-text">{isEn ? "First observed failure: " : "ความล้มเหลวแรกที่พบ: "}</span><span className="font-mono text-xs">{incident.firstMeaningfulFailure}</span></p>
            )}
            {incident.terminalFailure && (
              <p><span className="font-medium text-eims-text">{isEn ? "Terminal failure: " : "ความล้มเหลวสุดท้าย: "}</span><span className="font-mono text-xs">{incident.terminalFailure}</span></p>
            )}
            {incident.operationStage && (
              <p><span className="font-medium text-eims-text">{isEn ? "Operation stage: " : "ขั้นตอนการทำงาน: "}</span>{incident.operationStage}</p>
            )}
            {(incident.observedPaths || []).length > 0 && (
              <div>
                <p className="font-medium text-eims-text mb-1">{isEn ? "Observed paths:" : "พาธที่พบจริง:"}</p>
                <ul className="list-disc pl-4 space-y-1">
                  {(incident.observedPaths || []).map((p: string, idx: number) => (
                    <li key={idx} className="font-mono text-xs break-all">{p}</li>
                  ))}
                </ul>
              </div>
            )}
            {(incident.timeline || []).length > 0 && (
              <div>
                <p className="font-medium text-eims-text mb-1">{isEn ? "Timeline:" : "ไทม์ไลน์:"}</p>
                <ul className="list-disc pl-4 space-y-1">
                  {(incident.timeline || []).map((t: string, idx: number) => (
                    <li key={idx} className="font-mono text-xs">{t}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Evidence with file provenance */}
      {evidenceItems.length > 0 && (
        <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
          <h4 className="text-md font-semibold text-eims-text mb-3">
            {isEn ? "Observed Evidence (with source file)" : "หลักฐานที่พบ (พร้อมไฟล์ต้นทาง)"}
          </h4>
          <ul className="space-y-2">
            {evidenceItems.map((item: any, idx: number) => (
              <li key={idx} className="text-xs border-l-2 border-eims-border pl-3">
                <span className="font-mono text-eims-text-secondary break-all">{item.message}</span>
                <span className="block text-eims-text-muted mt-0.5">
                  {item.sourceFile}{item.lineNumber ? `:${item.lineNumber}` : ""}{item.timestamp ? ` · ${item.timestamp}` : ""}{item.observedPath ? ` · ${item.observedPath}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Interactive Chat Interface */}
      <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
        <h4 className="text-md font-semibold text-eims-text mb-4 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-eims-info dark:text-sky-400" /> {isEn ? "Ask Follow-up Questions" : "ถามรายละเอียดเพิ่มเติม"}
        </h4>
        <div className="flex gap-3">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submitFollowUp(); }}
            placeholder={isEn ? "Ask follow-up questions about this event..." : "ถามคำถามเกี่ยวกับ Event นี้ เช่น จะหาเหตุผลหรือแก้ไขอย่างไร..."}
            className="flex-1 bg-eims-bg border border-eims-border rounded-lg px-4 py-2 text-sm text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-info transition-colors"
          />
          <button
            onClick={submitFollowUp}
            disabled={asking || !question.trim()}
            className="bg-eims-info/20 hover:bg-eims-info/30 border border-eims-info/30 text-eims-info dark:text-sky-400 font-medium px-4 py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 shadow-sm whitespace-nowrap disabled:opacity-50"
          >
            <MessageSquare size={16} /> {asking ? (isEn ? "Asking..." : "กำลังถาม...") : (isEn ? "Ask AI" : "ถามเพิ่มเติม")}
          </button>
        </div>
        {askError && (
          <p className="text-xs text-red-500 mt-2">{askError}</p>
        )}
        {answer && (
          <div className="mt-3 text-sm text-eims-text-secondary leading-relaxed whitespace-pre-wrap border-t border-eims-border pt-3">
            {answer}
          </div>
        )}
      </div>

    </div>
  );
}
