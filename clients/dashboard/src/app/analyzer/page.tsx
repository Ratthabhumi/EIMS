"use client";

import { useState, useRef, useEffect } from "react";
import { Terminal, Upload, Play, Search, Save, FileText, Settings2, ShieldAlert, ArrowLeft, Download, History, X, Database } from "lucide-react";
import { toast } from "react-hot-toast";
import Link from "next/link";
import AnalyzerDashboard from "@/components/AnalyzerDashboard";
import AnalyzerHistoryList from "@/components/AnalyzerHistoryList";
import AnalysisResultDetail from "@/components/AnalysisResultDetail";
import SystemStatusCard from "@/components/SystemStatusCard";

export default function AnalyzerPage() {
  const [file, setFile] = useState<File | null>(null);
  const [rawText, setRawText] = useState("");
  const [uploadMode, setUploadMode] = useState<"file" | "text">("text");
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [language, setLanguage] = useState("th");
  const [isResultModalOpen, setIsResultModalOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  useEffect(() => {
    const handleGlobalPaste = (e: ClipboardEvent) => {
      // Don't interfere if the user is typing in a different input (though this page mostly has the textarea)
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' && (target as HTMLInputElement).type !== 'file') return;
      
      if (e.clipboardData?.files && e.clipboardData.files.length > 0) {
        const pastedFile = e.clipboardData.files[0];
        if (pastedFile.type.startsWith("image/")) {
          e.preventDefault();
          setFile(pastedFile);
          setUploadMode("file");
          toast.success("Image pasted from clipboard!");
        }
      } else if (e.clipboardData?.items) {
        // Handle text paste if we are not specifically focused on the textarea
        if (target.tagName !== 'TEXTAREA') {
          const pastedText = e.clipboardData.getData("text");
          if (pastedText && pastedText.trim().length > 0) {
            e.preventDefault();
            setRawText(prev => prev + pastedText);
            setUploadMode("text");
            toast.success("Text pasted from clipboard!");
          }
        }
      }
    };

    window.addEventListener("paste", handleGlobalPaste);
    return () => window.removeEventListener("paste", handleGlobalPaste);
  }, []);

  const handlePaste = (e: React.ClipboardEvent) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      const pastedFile = e.clipboardData.files[0];
      if (pastedFile.type.startsWith("image/")) {
        e.preventDefault();
        setFile(pastedFile);
        setUploadMode("file");
        toast.success("Image pasted from clipboard!");
      }
    }
  };

  const handleUpload = async () => {
    if (uploadMode === "file" && !file) {
      toast.error("Please select a file first.");
      return;
    }
    if (uploadMode === "text" && !rawText.trim()) {
      toast.error("Please paste some log text first.");
      return;
    }

    setIsUploading(true);
    toast.loading(uploadMode === "file" ? "Uploading file..." : "Sending text...", { id: "uploading" });

    try {
      const formData = new FormData();
      if (uploadMode === "file" && file) {
        formData.append("file", file);
      } else {
        formData.append("text", rawText);
      }
      formData.append("language", language);
      
      const res = await fetch("http://localhost:8000/api/v1/analyze/", {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) throw new Error("Failed to upload file");
      const data = await res.json();
      setResult(data);
      setIsResultModalOpen(true);
      setRefreshTrigger(prev => prev + 1);
      toast.success("Analysis complete", { id: "uploading" });
      
      // Clear input fields after successful analysis
      setRawText("");
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      toast.error("Error during upload or analysis.", { id: "uploading" });
    } finally {
      setIsUploading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!result) return;
    
    let content = `# AI Diagnostic Report\n\n`;
    content += `**Event ID:** ${result.eventId}\n`;
    content += `**Provider:** ${result.provider}\n`;
    content += `**Date:** ${new Date().toLocaleString()}\n\n`;
    
    if (result.aiSummary) {
      content += `## AI Summary\n\n${result.aiSummary}\n\n`;
    }
    
    if (result.solutionSummary) {
      content += `## Executive Summary\n${result.solutionSummary.overview || "N/A"}\n\n`;
      content += `## Root Causes\n`;
      (result.solutionSummary.causes || []).forEach((c: string) => { content += `- ${c}\n`; });
      content += `\n## Resolution Steps\n`;
      (result.solutionSummary.steps || []).forEach((s: string) => { content += `${s}\n`; });
    }
    
    if (result.searchResults && result.searchResults.length > 0) {
      content += `\n## References\n`;
      result.searchResults.forEach((r: any) => { content += `- [${r.title}](${r.link})\n`; });
    }

    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Log_Analysis_${result.eventId || "Report"}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Markdown report downloaded!");
  };

  const downloadPDF = async () => {
    if (!result) return;
    const toastId = toast.loading("Generating PDF...");
    try {
      const { default: jsPDF } = await import("jspdf");
      const { default: html2canvas } = await import("html2canvas");

      // Build a hidden div with the report content
      const container = document.createElement("div");
      container.style.cssText = "position:fixed;top:-9999px;left:-9999px;width:794px;padding:40px;background:#fff;font-family:Arial,sans-serif;font-size:13px;color:#242321;line-height:1.6;";

      const steps = result.solutionSummary?.steps || [];
      const causes = result.solutionSummary?.causes || [];
      const refs = result.searchResults || [];
      const meta = result.eventMetadata || {};

      container.innerHTML = `
        <h1 style="font-size:20px;font-weight:700;border-bottom:2px solid #68735C;padding-bottom:8px;margin-bottom:12px;">
          Diagnostic Report â€” Event ID: ${result.eventId || "Unknown"}
        </h1>
        <p style="color:#716E66;margin-bottom:20px;">Provider: <strong>${result.provider || "Unknown"}</strong> &nbsp;|&nbsp; Generated: ${new Date().toLocaleString()}</p>

        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Event Metadata</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          <div><span style="color:#716E66;font-size:11px;">Level</span><br/><strong>${meta.level || "Error"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Log Name</span><br/><strong>${meta.logName || "Application"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Time</span><br/><strong>${meta.timestamp || "N/A"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Computer</span><br/><strong>${meta.computer || "Localhost"}</strong></div>
          ${meta.faultingApp ? `<div style="grid-column:1/-1"><span style="color:#716E66;font-size:11px;">Faulting App</span><br/><strong style="color:#dc2626;">${meta.faultingApp}</strong></div>` : ""}
        </div>

        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Summary</h2>
        <div style="background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">${result.solutionSummary?.overview || result.aiSummary || "No summary available."}</div>

        ${causes.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Root Causes</h2><ul style="padding-left:20px;margin-bottom:12px;">${causes.map((c: string) => `<li style="margin-bottom:4px;">${c}</li>`).join("")}</ul>` : ""}

        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Resolution Steps</h2>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          ${steps.length > 0 ? `<ol style="padding-left:20px;margin:0;">${steps.map((s: string) => `<li style="margin-bottom:6px;">${s}</li>`).join("")}</ol>` : "<p>No specific steps provided.</p>"}
        </div>

        ${refs.length > 0 ? `
          <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">References</h2>
          ${refs.map((r: any) => `
            <div style="border:1px solid #D8D4CA;border-radius:6px;padding:8px 12px;margin-bottom:8px;">
              <div style="color:#1d4ed8;font-weight:500;">${r.title}</div>
              <div style="font-size:11px;color:#9A968D;margin:2px 0;">${r.link}</div>
              <div style="font-size:12px;color:#716E66;">${r.snippet || ""}</div>
            </div>
          `).join("")}
        ` : ""}
      `;

      document.body.appendChild(container);
      const canvas = await html2canvas(container, { scale: 2, useCORS: true, backgroundColor: "#fff" });
      document.body.removeChild(container);

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
      const pageW = pdf.internal.pageSize.getWidth();
      const pageH = pdf.internal.pageSize.getHeight();
      const imgW = pageW;
      const imgH = (canvas.height * imgW) / canvas.width;

      let y = 0;
      while (y < imgH) {
        if (y > 0) pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, -y, imgW, imgH);
        y += pageH;
      }

      pdf.save(`Diagnostic_Report_${result.eventId || "Unknown"}.pdf`);
      toast.success("PDF downloaded!", { id: toastId });
    } catch (err) {
      console.error(err);
      toast.error("Failed to generate PDF.", { id: toastId });
    }
  };

  return (
    <div className="animate-fade-in flex flex-col gap-5 pb-4">
      <header className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-eims-text flex items-center gap-3">
              <Terminal className="w-7 h-7 text-eims-accent" />
              AI Log Analyzer (EventIQ)
            </h1>
            <p className="text-sm text-eims-text-secondary mt-1">Upload Windows EVTX or raw log files for intelligent RCA.</p>
          </div>
        </div>
        {/* No View Dashboard button needed anymore */}
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">

        {/* LEFT SIDEBAR (col 1 on xl) */}
        <div className="xl:col-span-1 space-y-4 w-full">

          {/* Upload Source */}
          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text mb-4 uppercase tracking-wider flex items-center gap-2">
              <Upload className="w-3.5 h-3.5 text-eims-text-secondary" />
              Upload Source
            </h2>
            <div className="flex gap-2 mb-4 bg-eims-bg p-1 rounded-lg">
              <button
                onClick={() => setUploadMode("text")}
                className={`flex-1 text-xs font-medium py-1.5 rounded-md transition-colors ${uploadMode === "text" ? "bg-eims-surface text-eims-text shadow-sm" : "text-eims-text-muted hover:text-eims-text"}`}
              >Paste Text</button>
              <button
                onClick={() => setUploadMode("file")}
                className={`flex-1 text-xs font-medium py-1.5 rounded-md transition-colors ${uploadMode === "file" ? "bg-eims-surface text-eims-text shadow-sm" : "text-eims-text-muted hover:text-eims-text"}`}
              >File Upload</button>
            </div>
            {uploadMode === "file" ? (
              <div
                className="border-2 border-dashed border-eims-border rounded-lg p-6 text-center cursor-pointer hover:border-eims-accent transition-colors bg-eims-bg"
                onClick={() => fileInputRef.current?.click()}
                onPaste={handlePaste}
                tabIndex={0}
              >
                <input type="file" className="hidden" ref={fileInputRef} onChange={handleFileChange} accept="image/*,.evtx,.txt,.log,.xml,.csv" />
                <FileText className="w-7 h-7 text-eims-text-muted mx-auto mb-2" />
                <p className="text-xs font-medium text-eims-text">{file ? file.name : "Click or paste (Ctrl+V) image"}</p>
                <p className="text-xs text-eims-text-muted mt-1">EVTX, XML, Image, CSV, LOG</p>
              </div>
            ) : (
              <textarea
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                onPaste={handlePaste}
                placeholder="Paste raw Event Viewer log text..."
                className="w-full h-[130px] p-3 text-xs bg-eims-bg border border-eims-border rounded-lg text-eims-text placeholder-eims-text-muted resize-none focus:outline-none focus:border-eims-accent transition-colors"
              />
            )}
            <button
              onClick={handleUpload}
              disabled={(uploadMode === "file" ? !file : !rawText) || isUploading || isAnalyzing}
              className="mt-3 w-full bg-eims-accent hover:bg-eims-accent-hover text-white py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {(isUploading || isAnalyzing) ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Play className="w-4 h-4" />}
              {isUploading ? "Uploading..." : isAnalyzing ? "Analyzing..." : "Analyze Log"}
            </button>
          </div>

          {/* Analysis Engine */}
          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text mb-4 uppercase tracking-wider flex items-center gap-2">
              <Settings2 className="w-3.5 h-3.5 text-eims-text-secondary" />
              Analysis Engine
            </h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-eims-text-secondary">AI Model</span>
                <span className="text-xs font-medium text-eims-text bg-eims-bg px-2 py-1 rounded border border-eims-border">Local Offline DB</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-eims-text-secondary">Language</span>
                <select value={language} onChange={(e) => setLanguage(e.target.value)} className="text-xs font-medium text-eims-text bg-eims-bg px-2 py-1 rounded border border-eims-border focus:outline-none focus:border-eims-accent cursor-pointer">
                  <option value="th">Thai (TH)</option>
                  <option value="en">English (EN)</option>
                </select>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-eims-text-secondary">Vector RAG</span>
                <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded border border-emerald-200">Enabled</span>
              </div>
            </div>
          </div>

          {/* System Status */}
          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text uppercase tracking-wider flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              System Status
            </h2>
            <SystemStatusCard />
          </div>

          {/* Common Event IDs */}
          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text uppercase tracking-wider flex items-center gap-2 mb-3">
              <Database className="w-3.5 h-3.5 text-eims-text-secondary" />
              Common Event IDs
            </h2>
            <div className="space-y-1.5">
              {[
                { id: "41",   name: "Kernel-Power",  color: "error",   desc: "Unexpected reboot" },
                { id: "1000", name: "App Error",      color: "error",   desc: "Application crash" },
                { id: "1001", name: "Win Error",      color: "error",   desc: "BugCheck / BSOD" },
                { id: "6008", name: "EventLog",       color: "warning", desc: "Unexpected shutdown" },
                { id: "7034", name: "Service Ctrl",   color: "warning", desc: "Service crashed" },
                { id: "4625", name: "Security",       color: "warning", desc: "Failed logon" },
                { id: "4624", name: "Security",       color: "info",    desc: "Successful logon" },
                { id: "7036", name: "Service Ctrl",   color: "info",    desc: "Svc started/stopped" },
              ].map((item) => (
                <div key={item.id} className="flex items-center gap-2 text-xs py-1 border-b border-eims-border/40 last:border-0">
                  <span className={`font-mono font-bold w-10 shrink-0 ${ 
                    item.color === "error" ? "text-eims-error" : 
                    item.color === "warning" ? "text-eims-warning" : "text-eims-info" 
                  }`}>{item.id}</span>
                  <span className="text-eims-text">{item.name}</span>
                  <span className="text-eims-text-muted ml-auto text-[10px]">{item.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT (col 2-4 on xl): Dashboard + History */}
        <div className="xl:col-span-3 space-y-4 w-full">
          <AnalyzerDashboard refreshTrigger={refreshTrigger} />
          <AnalyzerHistoryList refreshTrigger={refreshTrigger} />
        </div>

      </div>
      {/* Result Popup Modal */}
      {isResultModalOpen && result && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 sm:p-6 animate-in fade-in duration-200">
          <div className="bg-eims-bg border border-eims-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[95vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-eims-border bg-eims-surface shrink-0">
              <h2 className="text-xl font-semibold text-eims-text flex items-center gap-3">
                <FileText className="w-6 h-6 text-eims-accent" />
                Diagnostic Report
              </h2>
              <div className="flex items-center gap-2">
                <button 
                  onClick={downloadMarkdown}
                  className="flex items-center gap-2 px-3 py-1.5 bg-eims-bg hover:bg-eims-surface-subtle border border-eims-border rounded-lg text-sm font-medium text-eims-text transition-colors"
                >
                  <Download size={14} /> Export MD
                </button>
                <button 
                  onClick={downloadPDF}
                  className="flex items-center gap-2 px-3 py-1.5 bg-eims-accent hover:bg-eims-accent/80 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  <Download size={14} /> Export PDF
                </button>
                <button 
                  onClick={() => setIsResultModalOpen(false)}
                  className="p-2 hover:bg-eims-surface-subtle rounded-full text-eims-text-muted hover:text-eims-text transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            
            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 flex flex-col gap-8">
              <AnalysisResultDetail 
                result={result} 
                language={language}
                onDownloadMD={downloadMarkdown} 
              />
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

