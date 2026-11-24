"use client";

import { escapeReportData } from '@/lib/report-data';
import { useState, useRef, useEffect, useCallback, useMemo, Suspense } from "react";
import { Terminal, Upload, Play, Search, Save, FileText, Settings2, ShieldAlert, ArrowLeft, Download, History, X, Database } from "lucide-react";
import { toast } from "react-hot-toast";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import AnalyzerDashboard from "@/components/AnalyzerDashboard";
import AnalyzerHistoryList, { type AnalyzerMainTab } from "@/components/AnalyzerHistoryList";
import AnalysisResultDetail from "@/components/AnalysisResultDetail";
import SystemStatusCard from "@/components/SystemStatusCard";
import EventIncidentLink from "@/components/incidents/EventIncidentLink";
import { apiUrl } from "@/lib/api";
import { type IncidentAssociation } from "@/lib/incident-orchestration";
import { knowledgeMatchHtml, knowledgeMatchMarkdown } from "@/components/KnowledgeMatchBadge";
import { downloadHtmlAsPdf, preloadPdfExport } from "@/lib/pdf-export";
import { readPortalPreferences, writePortalPreferences } from "@/lib/portal-preferences";
import { EVIDENCE_LIMITS } from "@/lib/ui-i18n";

function AnalyzerPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [file, setFile] = useState<File | null>(null);
  const [bundleFiles, setBundleFiles] = useState<File[]>([]);
  const [rawText, setRawText] = useState("");
  const [uploadMode, setUploadMode] = useState<"file" | "text" | "bundle">("text");
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<any>(null);
  /** Analysis report output language — not Portal UI language. */
  const [language, setLanguage] = useState<"th" | "en">("en");
  const [isResultModalOpen, setIsResultModalOpen] = useState(false);
  const [incidentAssociation, setIncidentAssociation] = useState<IncidentAssociation | null>(null);

  useEffect(() => {
    const pref = readPortalPreferences().analyzerLanguage;
    setLanguage(pref === "th" ? "th" : "en");
  }, []);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const bundleInputRef = useRef<HTMLInputElement>(null);
  const leftColRef = useRef<HTMLDivElement>(null);
  const [leftColHeight, setLeftColHeight] = useState<number | null>(null);
  const [sessionSearchLatencies, setSessionSearchLatencies] = useState<number[]>([]);
  const [incidentId, setIncidentId] = useState<string | null>(() => {
    const fromUrl = (searchParams.get("incident") || "").trim();
    return fromUrl || null;
  });
  const [linkedAnalysisId, setLinkedAnalysisId] = useState<number | null>(() => {
    const analysisRaw = searchParams.get("analysis");
    return analysisRaw && /^\d+$/.test(analysisRaw) ? Number(analysisRaw) : null;
  });
  const [mainTab, setMainTab] = useState<AnalyzerMainTab>(() =>
    (searchParams.get("incident") || "").trim() ? "incident" : "history",
  );

  const handleSearchLatency = useCallback((latencyMs: number) => {
    setSessionSearchLatencies(prev => [...prev, latencyMs]);
  }, []);

  const syncIncidentUrl = useCallback((nextIncident: string | null, analysisId: number | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (nextIncident) params.set("incident", nextIncident);
    else params.delete("incident");
    if (analysisId != null) params.set("analysis", String(analysisId));
    else params.delete("analysis");
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  useEffect(() => {
    const fromUrl = (searchParams.get("incident") || "").trim();
    if (fromUrl) {
      setIncidentId(fromUrl);
      setMainTab("incident");
    } else {
      setIncidentId(null);
    }
    const analysisRaw = searchParams.get("analysis");
    if (analysisRaw && /^\d+$/.test(analysisRaw)) {
      setLinkedAnalysisId(Number(analysisRaw));
    }
  }, [searchParams]);

  const openIncident = useCallback((id: string, analysisId?: number | null) => {
    setIncidentId(id);
    setMainTab("incident");
    setIsResultModalOpen(false);
    if (typeof analysisId === "number") setLinkedAnalysisId(analysisId);
    syncIncidentUrl(id, typeof analysisId === "number" ? analysisId : linkedAnalysisId);
  }, [linkedAnalysisId, syncIncidentUrl]);

  /** Close selected incident detail → Incident list landing; stay on Incident Workspace tab. */
  const closeIncidentDetail = useCallback(() => {
    setIncidentId(null);
    setMainTab("incident");
    syncIncidentUrl(null, linkedAnalysisId);
  }, [linkedAnalysisId, syncIncidentUrl]);

  const avgSearchTimeMs = useMemo(() => {
    if (sessionSearchLatencies.length === 0) return null;
    const sum = sessionSearchLatencies.reduce((a, b) => a + b, 0);
    return sum / sessionSearchLatencies.length;
  }, [sessionSearchLatencies]);

  useEffect(() => {
    if (result && isResultModalOpen) {
      void preloadPdfExport().catch((error) => console.warn("PDF export preload failed", error));
    }
  }, [result, isResultModalOpen]);

  useEffect(() => {
    if (!leftColRef.current) return;
    const updateHeight = () => {
      if (leftColRef.current) {
        setLeftColHeight(leftColRef.current.offsetHeight);
      }
    };
    updateHeight();
    const ro = new ResizeObserver(updateHeight);
    ro.observe(leftColRef.current);
    window.addEventListener("resize", updateHeight);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", updateHeight);
    };
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleBundleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const picked = Array.from(e.target.files).slice(0, EVIDENCE_LIMITS.maxFiles);
      setBundleFiles((prev) => {
        const names = new Set(prev.map((f) => f.name));
        const merged = [...prev];
        for (const f of picked) {
          if (!names.has(f.name)) {
            merged.push(f);
            names.add(f.name);
          }
        }
        return merged.slice(0, EVIDENCE_LIMITS.maxFiles);
      });
    }
  };

  const removeBundleFile = (name: string) => {
    setBundleFiles((prev) => prev.filter((f) => f.name !== name));
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
      toast.error("Please select a file first");
      return;
    }
    if (uploadMode === "text" && !rawText.trim()) {
      toast.error("Please paste some text first");
      return;
    }
    if (uploadMode === "bundle" && bundleFiles.length === 0) {
      toast.error("Please add at least one evidence file");
      return;
    }

    setIsUploading(true);
    toast.loading(
      uploadMode === "bundle"
        ? "Uploading evidence bundle…"
        : uploadMode === "file"
          ? "Uploading file…"
          : "Sending text…",
      { id: "uploading" },
    );

    try {
      const formData = new FormData();
      let endpoint = "/api/v1/analyze/";
      if (uploadMode === "bundle") {
        for (const f of bundleFiles) {
          formData.append("files", f);
        }
        endpoint = "/api/v1/analyze/bundle";
      } else if (uploadMode === "file" && file) {
        formData.append("file", file);
      } else {
        formData.append("text", rawText);
      }
      formData.append("language", language);

      const res = await fetch(apiUrl(endpoint), {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        let detail = "Failed to upload file";
        try {
          const err = await res.json();
          detail = err.detail || detail;
        } catch {}
        throw new Error(detail);
      }
      const data = await res.json();
      setResult(data);
      setIncidentAssociation(null);
      setIsResultModalOpen(true);
      setRefreshTrigger(prev => prev + 1);
      toast.success("Analysis complete — associating incident…", { id: "uploading" });

      // Clear input fields after successful analysis
      setRawText("");
      setFile(null);
      setBundleFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (bundleInputRef.current) {
        bundleInputRef.current.value = "";
      }
    } catch (error: any) {
      toast.error(error?.message || "Error during upload or analysis.", { id: "uploading" });
    } finally {
      setIsUploading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!result) return;
    
    let content = `# AI Diagnostic Report\n\n`;
    const diagCode = result.eventMetadata?.diagnosticCode || "";
    const product = result.eventMetadata?.product || "";
    content += diagCode
      ? `**Source:** ${product || result.provider || "Not provided"}\n**Diagnostic Code:** ${diagCode}\n**Event ID:** ${result.eventId || "Not provided"}\n`
      : `**Event ID:** ${result.eventId || "Not provided"}\n`;
    content += `**Provider:** ${result.provider || "Not provided"}\n`;
    content += `**Generated:** ${new Date().toLocaleString()}\n`;
    content += knowledgeMatchMarkdown(result.solutionSummary?.knowledgeMatch) + "\n";
    
    if (result.aiSummary) {
      content += `## AI Summary\n\n${result.aiSummary}\n\n`;
    }
    
    if (result.solutionSummary) {
      content += `## Executive Summary\n${result.solutionSummary.overview || "N/A"}\n\n`;
      content += `## Possible Causes / Assessment\n`;
      (result.solutionSummary.causes || []).forEach((c: string) => { content += `- ${c}\n`; });
      content += `\n## Recommended Next Steps\n`;
      (result.solutionSummary.steps || []).forEach((s: string) => { content += `${s}\n`; });
      if (result.solutionSummary.evidence && result.solutionSummary.evidence.length > 0) {
        content += `\n## Observed Evidence\n`;
        result.solutionSummary.evidence.forEach((e: string) => { content += `- ${e}\n`; });
        if (result.solutionSummary.confidence) content += `\nConfidence: ${result.solutionSummary.confidence}\n`;
      }
      if (result.solutionSummary.evidenceItems?.length) {
        content += `\n## Extracted Source Evidence\n`;
        result.solutionSummary.evidenceItems.forEach((e: any) => {
          content += `- ${e.sourceFile || "Not provided"}:${e.lineNumber ?? "Not provided"} — ${e.message || "Not provided"}\n`;
        });
      }
      if (result.solutionSummary.limitations && result.solutionSummary.limitations.length > 0) {
        content += `\n## What Is Still Unknown\n`;
        result.solutionSummary.limitations.forEach((u: string) => { content += `- ${u}\n`; });
      }
      if (result.solutionSummary.nextEvidence && result.solutionSummary.nextEvidence.length > 0) {
        content += `\n## Next Evidence to Collect\n`;
        result.solutionSummary.nextEvidence.forEach((n: string) => { content += `- ${n}\n`; });
      }
    }
    
    if (result.searchResults && result.searchResults.length > 0) {
      content += `\n## References\n`;
      result.searchResults.forEach((r: any) => { content += `- [${r.title}](${r.link})${r.sourceType && r.sourceType !== "official" ? " (community)" : ""}\n`; });
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
    const safeResult = escapeReportData(result);
    if (!safeResult) return;
    const toastId = toast.loading("Generating PDF...");
    try {
      // Keep the sanitized report in the DOM but invisible; html2canvas reveals it only in its clone.
      const container = document.createElement("div");
      container.dataset.eimsPdfExport = "true";
      container.style.cssText = "position:fixed;top:0;left:0;width:794px;padding:40px;background:#fff;font-family:Arial,sans-serif;font-size:13px;color:#242321;line-height:1.6;opacity:0;pointer-events:none;z-index:-1;";

      const steps = safeResult.solutionSummary?.steps || [];
      const causes = safeResult.solutionSummary?.causes || [];
      const refs = safeResult.searchResults || [];
      const meta = safeResult.eventMetadata || {};
      const evList: string[] = safeResult.solutionSummary?.evidence || [];
      const unknowns: string[] = safeResult.solutionSummary?.limitations || [];
      const nextEv: string[] = safeResult.solutionSummary?.nextEvidence || [];
      const conf: string = safeResult.solutionSummary?.confidence || "";
      const diagCode: string = meta.diagnosticCode || "";
      const product: string = meta.product || "";
      const titleLine = diagCode
        ? `${product || safeResult.provider || "Not provided"} — ${diagCode} — Event ID: ${safeResult.eventId || "Not provided"}`
        : `Event ID: ${safeResult.eventId || "Unknown"}`;

      container.innerHTML = `
        <h1 style="font-size:20px;font-weight:700;border-bottom:2px solid #68735C;padding-bottom:8px;margin-bottom:12px;">
          Diagnostic Report — ${titleLine}
        </h1>
        <p style="color:#716E66;margin-bottom:20px;">Provider: <strong>${safeResult.provider || "Unknown"}</strong> &nbsp;|&nbsp; Generated: ${new Date().toLocaleString()}</p>

        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Event Metadata</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          <div><span style="color:#716E66;font-size:11px;">Level</span><br/><strong>${meta.level || "Not provided"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Log Name</span><br/><strong>${meta.logName || "Not provided"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Time</span><br/><strong>${meta.timestamp || "Not provided"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Computer</span><br/><strong>${meta.computer || "Not provided"}</strong></div>
          ${meta.faultingApp ? `<div style="grid-column:1/-1"><span style="color:#716E66;font-size:11px;">Faulting App</span><br/><strong style="color:#dc2626;">${meta.faultingApp}</strong></div>` : ""}
        </div>

        ${knowledgeMatchHtml(safeResult.solutionSummary?.knowledgeMatch)}
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Summary</h2>
        <div style="background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">${safeResult.solutionSummary?.overview || safeResult.aiSummary || "No summary available."}</div>

        ${causes.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Possible Causes / Assessment</h2><ul style="padding-left:20px;margin-bottom:12px;">${causes.map((c: string) => `<li style="margin-bottom:4px;">${c}</li>`).join("")}</ul>` : ""}

        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Recommended Next Steps</h2>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          ${steps.length > 0 ? `<ol style="padding-left:20px;margin:0;">${steps.map((s: string) => `<li style="margin-bottom:6px;">${s}</li>`).join("")}</ol>` : "<p>No specific steps provided.</p>"}
        </div>

        ${evList.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Observed Evidence${conf ? ` (confidence: ${conf})` : ""}</h2><ul style="padding-left:20px;margin-bottom:12px;">${evList.map((e: string) => `<li style="margin-bottom:4px;">${e}</li>`).join("")}</ul>` : ""}
        ${safeResult.solutionSummary?.evidenceItems?.length ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Extracted Source Evidence</h2><ul>${safeResult.solutionSummary.evidenceItems.map((e: any) => `<li>${e.sourceFile || "Not provided"}:${e.lineNumber ?? "Not provided"} — ${e.message || "Not provided"}</li>`).join("")}</ul>` : ""}
        ${unknowns.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">What Is Still Unknown</h2><ul style="padding-left:20px;margin-bottom:12px;">${unknowns.map((u: string) => `<li style="margin-bottom:4px;">${u}</li>`).join("")}</ul>` : ""}
        ${nextEv.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Next Evidence to Collect</h2><ul style="padding-left:20px;margin-bottom:12px;">${nextEv.map((n: string) => `<li style="margin-bottom:4px;">${n}</li>`).join("")}</ul>` : ""}

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
      try {
        const pdfResult = await downloadHtmlAsPdf(
          container,
          `Diagnostic_Report_${safeResult.eventId || "Unknown"}.pdf`,
        );
        toast.success(`PDF downloaded (${pdfResult.pages} pages).`, { id: toastId });
      } finally {
        container.remove();
      }
    } catch (err) {
      console.error("PDF export failed", err);
      const message = err instanceof Error ? err.message : String(err);
      toast.error(`Failed to generate PDF: ${message.slice(0, 120)}`, { id: toastId });
    }
  };

  return (
    <div className="animate-fade-in flex flex-col gap-5 pb-4">
      <header className="flex items-center justify-between shrink-0 gap-3 min-w-0">
        <div className="flex items-center gap-4 min-w-0">
          <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-[28px] font-semibold tracking-tight text-eims-text flex items-center gap-3">
              <Terminal className="w-7 h-7 text-eims-accent shrink-0" />
              Log Analyzer
            </h1>
            <p className="text-sm text-eims-text-secondary mt-1">
              Drop in your evidence and find the root cause fast. Incident Workspace lives in its own main tab, not a side drawer.
            </p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">

        {/* LEFT SIDEBAR (col 1 on xl) */}
        <div ref={leftColRef} className="xl:col-span-1 space-y-4 w-full">

          {/* Evidence Input — one UX surface; backend parsers remain type-specific */}
          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm" data-testid="evidence-input">
            <h2 className="text-xs font-semibold text-eims-text mb-1 uppercase tracking-wider flex items-center gap-2">
              <Upload className="w-3.5 h-3.5 text-eims-text-secondary" />
              Evidence Input
            </h2>
            <p className="text-[11px] text-eims-text-muted mb-3">One submission path for Analyzer. Choose how you provide evidence; parsers stay type-specific.</p>
            <div className="flex gap-1 mb-3 bg-eims-bg p-1 rounded-lg" role="tablist" aria-label="Evidence Input">
              <button type="button" role="tab" aria-selected={uploadMode === "text"} onClick={() => setUploadMode("text")}
                className={`flex-1 text-[11px] font-medium py-1.5 px-1 rounded-md transition-colors ${uploadMode === "text" ? "bg-eims-surface text-eims-text shadow-sm" : "text-eims-text-muted hover:text-eims-text"}`}
              >Paste Log Text</button>
              <button type="button" role="tab" aria-selected={uploadMode === "file"} onClick={() => setUploadMode("file")}
                className={`flex-1 text-[11px] font-medium py-1.5 px-1 rounded-md transition-colors ${uploadMode === "file" ? "bg-eims-surface text-eims-text shadow-sm" : "text-eims-text-muted hover:text-eims-text"}`}
              >Upload Files</button>
              <button type="button" role="tab" aria-selected={uploadMode === "bundle"} onClick={() => setUploadMode("bundle")}
                className={`flex-1 text-[11px] font-medium py-1.5 px-1 rounded-md transition-colors ${uploadMode === "bundle" ? "bg-eims-surface text-eims-text shadow-sm" : "text-eims-text-muted hover:text-eims-text"}`}
              >Upload Evidence Bundle</button>
            </div>
            {uploadMode === "bundle" ? (
              <div>
                <p className="text-[11px] text-eims-text-secondary mb-2">
                  Multiple related files as one evidence set (not a ZIP). Up to {EVIDENCE_LIMITS.maxFiles} files · {EVIDENCE_LIMITS.maxFileMb} MB each · {EVIDENCE_LIMITS.maxTotalMb} MB total. Types: {EVIDENCE_LIMITS.extensions}.
                </p>
                <div className="border-2 border-dashed border-eims-border rounded-lg p-6 text-center cursor-pointer hover:border-eims-accent transition-colors bg-eims-bg"
                  onClick={() => bundleInputRef.current?.click()} tabIndex={0}>
                  <input type="file" multiple className="hidden" ref={bundleInputRef} onChange={handleBundleChange} accept={EVIDENCE_LIMITS.acceptAttr} />
                  <FileText className="w-7 h-7 text-eims-text-muted mx-auto mb-2" />
                  <p className="text-xs font-medium text-eims-text">Click to add related evidence files</p>
                  <p className="text-xs text-eims-text-muted mt-1">ZIP archives are not accepted — select individual files so each keeps its own metadata and hash.</p>
                </div>
                {bundleFiles.length > 0 && (
                  <ul className="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                    {bundleFiles.map((f) => (
                      <li key={f.name} className="flex items-center gap-2 text-xs bg-eims-bg border border-eims-border rounded-lg px-2.5 py-1.5">
                        <span className="font-mono text-eims-text truncate flex-1">{f.name}</span>
                        <span className="text-eims-text-muted shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                        <button onClick={() => removeBundleFile(f.name)} className="p-1 hover:bg-eims-surface-subtle rounded text-eims-text-muted hover:text-eims-text shrink-0" aria-label={`Remove ${f.name}`}>
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : uploadMode === "file" ? (
              <div>
                <p className="text-[11px] text-eims-text-secondary mb-2">Single file. Supported: {EVIDENCE_LIMITS.extensions}. Max {EVIDENCE_LIMITS.maxFileMb} MB.</p>
                <div className="border-2 border-dashed border-eims-border rounded-lg p-6 text-center cursor-pointer hover:border-eims-accent transition-colors bg-eims-bg"
                  onClick={() => fileInputRef.current?.click()} onPaste={handlePaste} tabIndex={0}>
                  <input type="file" className="hidden" ref={fileInputRef} onChange={handleFileChange} accept={`image/*,${EVIDENCE_LIMITS.acceptAttr}`} />
                  <FileText className="w-7 h-7 text-eims-text-muted mx-auto mb-2" />
                  <p className="text-xs font-medium text-eims-text">{file ? file.name : "Click to choose a file (or paste image with Ctrl+V)"}</p>
                  <p className="text-xs text-eims-text-muted mt-1">Images require server-side Tesseract OCR. If unavailable, use text or a UTF-8 file.</p>
                </div>
              </div>
            ) : (
              <div>
                <p className="text-[11px] text-eims-text-secondary mb-2">Paste Event Viewer / log text. Original text is retained for analysis provenance.</p>
                <textarea value={rawText} onChange={(e) => setRawText(e.target.value)} onPaste={handlePaste}
                  placeholder="Paste raw Event Viewer log text…"
                  className="w-full h-[130px] p-3 text-xs bg-eims-bg border border-eims-border rounded-lg text-eims-text placeholder-eims-text-muted resize-none focus:outline-none focus:border-eims-accent transition-colors" />
              </div>
            )}
            <button onClick={handleUpload}
              disabled={(uploadMode === "file" ? !file : uploadMode === "bundle" ? bundleFiles.length === 0 : !rawText) || isUploading || isAnalyzing}
              className="mt-3 w-full bg-eims-accent hover:bg-eims-accent-hover text-white py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
              {(isUploading || isAnalyzing) ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Play className="w-4 h-4" />}
              {isUploading ? "Uploading…" : isAnalyzing ? "Analyzing…" : "Analyze Evidence"}
            </button>
          </div>

          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text mb-4 uppercase tracking-wider flex items-center gap-2">
              <Settings2 className="w-3.5 h-3.5 text-eims-text-secondary" />
              Analysis Engine
            </h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-eims-text-secondary">Analysis engine</span>
                <span className="text-xs font-medium text-eims-text bg-eims-bg px-2 py-1 rounded border border-eims-border">Local Offline DB</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-eims-text-secondary">Analysis output language</span>
                <select value={language}
                  onChange={(e) => {
                    const next = e.target.value === "th" ? "th" : "en";
                    setLanguage(next);
                    writePortalPreferences({ analyzerLanguage: next });
                  }}
                  className="text-xs font-medium text-eims-text bg-eims-bg px-2 py-1 rounded border border-eims-border focus:outline-none focus:border-eims-accent cursor-pointer"
                  aria-label="Analysis output language">
                  <option value="en">English (EN)</option>
                  <option value="th">Thai (TH)</option>
                </select>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-eims-text-secondary">Knowledge match</span>
                <span className="text-xs font-medium text-emerald-600/90 dark:text-[#78B096] bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20">Available</span>
              </div>
            </div>
          </div>

          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text uppercase tracking-wider flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-emerald-500/80 animate-pulse" />
              System Status
            </h2>
            <SystemStatusCard />
          </div>

          <div className="bg-eims-surface border border-eims-border rounded-xl p-5 shadow-sm">
            <h2 className="text-xs font-semibold text-eims-text uppercase tracking-wider flex items-center gap-2 mb-3">
              <Database className="w-3.5 h-3.5 text-eims-text-secondary" />
              Common Event IDs
            </h2>
            <div className="space-y-1.5">
              {[
                { id: "41",   name: "Kernel-Power",  color: "error",   desc: "Unexpected reboot" },
                { id: "4625", name: "Security",       color: "error",   desc: "Failed logon" },
                { id: "4740", name: "Security",       color: "error",   desc: "Account locked" },
                { id: "1102", name: "Security",       color: "error",   desc: "Audit log cleared" },
                { id: "1000", name: "App Error",      color: "error",   desc: "Application crash" },
                { id: "6008", name: "EventLog",       color: "warning", desc: "Unexpected shutdown" },
                { id: "7034", name: "Service Ctrl",   color: "warning", desc: "Service crashed" },
                { id: "4672", name: "Security",       color: "warning", desc: "Privileges assigned" },
                { id: "4104", name: "PowerShell",     color: "warning", desc: "Script block logged" },
                { id: "5152", name: "WFP",            color: "warning", desc: "Firewall blocked" },
                { id: "7045", name: "Service Ctrl",   color: "info",    desc: "Service installed" },
                { id: "1116", name: "Defender",       color: "info",    desc: "Threat detected" },
                { id: "4624", name: "Security",       color: "info",    desc: "Successful logon" },
                { id: "7036", name: "Service Ctrl",   color: "info",    desc: "Svc started/stopped" },
              ].map((item) => (
                <div key={item.id} className="flex items-center gap-2 text-xs py-1 border-b border-eims-border/40 last:border-0">
                  <span className={`font-mono font-semibold w-10 shrink-0 ${
                    item.color === "error" ? "text-rose-500/90 dark:text-[#D9777F]" :
                    item.color === "warning" ? "text-amber-500/90 dark:text-[#D4A373]" : "text-sky-500/90 dark:text-[#7EA8BE]"
                  }`}>{item.id}</span>
                  <span className="text-eims-text">{item.name}</span>
                  <span className="text-eims-text-muted ml-auto text-[10px]">{item.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* RIGHT (col 2-4 on xl): Dashboard + History */}
        <div
          className="xl:col-span-3 space-y-4 w-full flex flex-col min-h-0 xl:h-[var(--left-col-height)]"
          style={{ '--left-col-height': leftColHeight ? `${leftColHeight}px` : 'auto' } as React.CSSProperties}
        >
          <AnalyzerDashboard refreshTrigger={refreshTrigger} avgSearchTimeMs={avgSearchTimeMs} />
          <AnalyzerHistoryList
            refreshTrigger={refreshTrigger}
            onSearchLatency={handleSearchLatency}
            onOpenIncident={(id, analysisId) => openIncident(id, analysisId ?? linkedAnalysisId)}
            onCloseIncident={closeIncidentDetail}
            initialAnalysisId={linkedAnalysisId}
            correlationAssetId={(searchParams.get("asset") || "").trim() || null}
            incidentId={incidentId}
            activeTab={mainTab}
            onActiveTabChange={setMainTab}
            analysisLanguage={language}
            onIncidentChanged={(id) => {
              setIncidentId(id);
              syncIncidentUrl(id, linkedAnalysisId);
            }}
            className="flex-1 min-h-[400px] xl:min-h-0 flex flex-col"
          />
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
              {typeof result.historyId === "number" && (
                <EventIncidentLink
                  analysisHistoryId={result.historyId}
                  eventKey={result.eventId != null ? String(result.eventId) : undefined}
                  titleHint={
                    result.solutionSummary?.title
                      || (result.eventId != null ? `Event ${result.eventId}` : undefined)
                  }
                  assetId={(searchParams.get("asset") || "").trim() || null}
                  autoEnsure
                  onOpen={(incidentId) => {
                    setIsResultModalOpen(false);
                    openIncident(incidentId, result.historyId);
                  }}
                  onLinked={(_incidentId, association) => {
                    // Association is background work. Never auto-navigate away from Analysis Record Details.
                    // Ambiguous must never auto-open a candidate incident (onOpen is user-only).
                    setIncidentAssociation(association ?? null);
                    setRefreshTrigger((prev) => prev + 1);
                    if (association?.outcome === "created") toast.success("Incident created — review when ready");
                    else if (association?.outcome === "correlated") toast.success("Evidence linked to an existing incident");
                    else if (association?.outcome === "already_linked") toast.success("Evidence already linked");
                    else if (association?.outcome === "ambiguous") {
                      toast("Correlation ambiguous — review before treating as linked", { icon: "⚠️" });
                    } else if (association?.outcome === "failed") toast.error(association.message || "Incident association failed");
                    else if (association?.outcome === "unavailable") toast("Analysis complete — no incident association yet");
                  }}
                />
              )}
              {incidentAssociation?.outcome === "failed" ? (
                <p className="text-xs text-amber-700 dark:text-amber-300" role="status">
                  Analysis is available. Incident association failed — use Advanced linking or retry. Do not assume an incident exists.
                </p>
              ) : null}
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

export default function AnalyzerPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-eims-text-muted">Loading Log Analyzer…</div>}>
      <AnalyzerPageInner />
    </Suspense>
  );
}


