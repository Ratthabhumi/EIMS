import React from 'react';
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

  if (!result) return null;

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
  
  // Detect language: use language prop if explicitly provided, else detect from text (Thai character check)
  const isThaiText = (text: string) => /[\u0E00-\u0E7F]/.test(text);
  const detectedEn = !isThaiText(summary) && (!steps.length || !isThaiText(steps.join(" ")));
  const isEn = language ? language === "en" : detectedEn;

  return (
    <div className="flex flex-col gap-6 animate-fade-in w-full">
      
      {/* Header Box */}
      <div className="bg-eims-surface border-l-4 border-l-sky-500 border border-eims-border rounded-lg p-4 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
          <AlertCircle size={100} />
        </div>
        <h3 className="text-lg font-semibold text-eims-text flex items-center gap-2">
          Event ID: <span className="text-eims-info dark:text-sky-400 font-bold">{eventId}</span> - {provider}
          <span className="text-eims-text-secondary font-normal text-sm ml-2">{isEn ? "Number of events:" : "จำนวนเหตุการณ์:"} {numEvents}</span>
        </h3>
        <p className="text-eims-info dark:text-sky-400 text-sm mt-2 flex items-center gap-2">
          {parseMethod.includes("OCR") ? <FileImage size={14} /> : <FileText size={14} />}
          (Extracted via {parseMethod})
        </p>
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
            <p className="text-sm text-red-500 mb-1 font-medium">{isEn ? "Root Causes:" : "สาเหตุที่เป็นไปได้:"}</p>
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
                    Official
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
              if (result.id) {
                try {
                  await fetch(`http://localhost:8000/api/v1/history/${result.id}/feedback?score=1`, { method: "POST" });
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
              if (result.id) {
                try {
                  await fetch(`http://localhost:8000/api/v1/history/${result.id}/feedback?score=-1`, { method: "POST" });
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

      {/* Interactive Chat Interface */}
      <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
        <h4 className="text-md font-semibold text-eims-text mb-4 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-eims-info dark:text-sky-400" /> {isEn ? "Ask Follow-up Questions" : "ถามรายละเอียดเพิ่มเติม"}
        </h4>
        <div className="flex gap-3">
          <input 
            type="text" 
            placeholder={isEn ? "Ask follow-up questions about this event..." : "ถามคำถามเกี่ยวกับ Event นี้ เช่น จะหาเหตุผลหรือแก้ไขอย่างไร..."}
            className="flex-1 bg-eims-bg border border-eims-border rounded-lg px-4 py-2 text-sm text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-info transition-colors"
          />
          <button className="bg-eims-info/20 hover:bg-eims-info/30 border border-eims-info/30 text-eims-info dark:text-sky-400 font-medium px-4 py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 shadow-sm whitespace-nowrap">
            <MessageSquare size={16} /> {isEn ? "Ask AI" : "ถามเพิ่มเติม"}
          </button>
        </div>
      </div>

    </div>
  );
}
