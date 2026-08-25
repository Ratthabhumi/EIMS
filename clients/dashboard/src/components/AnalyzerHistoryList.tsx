import { useState, useEffect, useRef } from "react";
import { Search, Trash2, Code, FileImage, FileText, X, Download } from "lucide-react";
import { toast } from "react-hot-toast";
import AnalysisResultDetail from "./AnalysisResultDetail";

interface AnalyzerHistoryListProps {
  refreshTrigger?: number;
}

export default function AnalyzerHistoryList({ refreshTrigger = 0 }: AnalyzerHistoryListProps) {
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedItem, setSelectedItem] = useState<any | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  const fetchHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/history/");
      if (res.ok) {
        const data = await res.json();
        setHistoryList(data);
      }
    } catch (error) {
      console.error("Failed to fetch history");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [refreshTrigger]);

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this record?")) return;
    
    const loadingToast = toast.loading("Deleting...");
    try {
      const res = await fetch(`http://localhost:8000/api/v1/history/${id}`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("Failed to delete");
      toast.success("Deleted successfully", { id: loadingToast });
      setHistoryList(prev => prev.filter(item => item.id !== id));
    } catch (error) {
      toast.error("Failed to delete record", { id: loadingToast });
    }
  };

  const filteredHistory = historyList.filter(item => 
    (item.eventId && item.eventId.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (item.provider && item.provider.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  // Close modal when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        setSelectedItem(null);
      }
    };
    if (selectedItem) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [selectedItem]);

  const downloadMarkdown = (item: any) => {
    if (!item) return;
    let content = `# AI Diagnostic Report\n\n`;
    content += `**Event ID:** ${item.eventId}\n`;
    content += `**Provider:** ${item.provider}\n`;
    content += `**Date:** ${new Date(item.created_at).toLocaleString()}\n\n`;
    if (item.aiSummary) content += `## AI Summary\n\n${item.aiSummary}\n\n`;
    if (item.solutionSummary) {
      content += `## Executive Summary\n${item.solutionSummary.overview || "N/A"}\n\n`;
      content += `## Root Causes\n`;
      (item.solutionSummary.causes || []).forEach((c: string) => { content += `- ${c}\n`; });
      content += `\n## Resolution Steps\n`;
      (item.solutionSummary.steps || []).forEach((s: string) => { content += `${s}\n`; });
    }
    if (item.searchResults && item.searchResults.length > 0) {
      content += `\n## References\n`;
      item.searchResults.forEach((r: any) => { content += `- [${r.title}](${r.link})\n`; });
    }
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Log_Analysis_${item.eventId || "Report"}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Markdown report downloaded!");
  };

  const downloadPDF = async (item: any) => {
    if (!item) return;
    const toastId = toast.loading("Generating PDF...");
    try {
      const { default: jsPDF } = await import("jspdf");
      const { default: html2canvas } = await import("html2canvas");

      const container = document.createElement("div");
      container.style.cssText = "position:fixed;top:-9999px;left:-9999px;width:794px;padding:40px;background:#fff;font-family:Arial,sans-serif;font-size:13px;color:#242321;line-height:1.6;";

      const steps = item.solutionSummary?.steps || [];
      const causes = item.solutionSummary?.causes || [];
      const refs = item.searchResults || [];
      const meta = item.eventMetadata || {};

      container.innerHTML = `
        <h1 style="font-size:20px;font-weight:700;border-bottom:2px solid #68735C;padding-bottom:8px;margin-bottom:12px;">
          Diagnostic Report — Event ID: ${item.eventId || "Unknown"}
        </h1>
        <p style="color:#716E66;margin-bottom:20px;">Provider: <strong>${item.provider || "Unknown"}</strong> &nbsp;|&nbsp; Generated: ${new Date(item.created_at).toLocaleString()}</p>
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Event Metadata</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          <div><span style="color:#716E66;font-size:11px;">Level</span><br/><strong>${meta.level || "Error"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Log Name</span><br/><strong>${meta.logName || "Application"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Time</span><br/><strong>${meta.timestamp || "N/A"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Computer</span><br/><strong>${meta.computer || "Localhost"}</strong></div>
          ${meta.faultingApp ? `<div style="grid-column:1/-1"><span style="color:#716E66;font-size:11px;">Faulting App</span><br/><strong style="color:#dc2626;">${meta.faultingApp}</strong></div>` : ""}
        </div>
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Summary</h2>
        <div style="background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">${item.solutionSummary?.overview || item.aiSummary || "No summary available."}</div>
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

      pdf.save(`Diagnostic_Report_${item.eventId || "Unknown"}.pdf`);
      toast.success("PDF downloaded!", { id: toastId });
    } catch (err) {
      console.error(err);
      toast.error("Failed to generate PDF.", { id: toastId });
    }
  };

  return (
    <div className="bg-eims-surface border border-eims-border rounded-xl shadow-sm overflow-hidden flex flex-col">
      <div className="p-4 border-b border-eims-border flex items-center justify-between bg-eims-bg/50">
        <div className="relative w-64">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-eims-text-muted" />
          <input
            type="text"
            placeholder="Search Event ID or Provider..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-eims-bg border border-eims-border rounded-lg text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-accent transition-colors"
          />
        </div>
      </div>

      <div className="divide-y divide-eims-border max-h-[585px] overflow-y-auto custom-scrollbar">
        {isLoading ? (
          <div className="p-8 text-center text-eims-text-muted">Loading history...</div>
        ) : filteredHistory.length === 0 ? (
          <div className="p-8 text-center text-eims-text-muted">No records found.</div>
        ) : (
          filteredHistory.map((item) => (
            <div 
              key={item.id} 
              className="p-4 hover:bg-eims-surface-subtle transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 group cursor-pointer"
              onClick={() => setSelectedItem(item)}
            >
              <div className="min-w-0 flex-1">
                <h4 className="font-medium text-base sm:text-lg flex flex-wrap items-center gap-2">
                  <span className="text-eims-info dark:text-sky-400 group-hover:underline transition-colors">Event ID {item.eventId} - {item.provider}</span>
                  {item.eventMetadata?.faultingApp && (
                    <span className="bg-eims-surface-subtle text-eims-text-secondary border border-eims-border text-xs px-2 py-0.5 rounded truncate max-w-full font-mono">
                      {item.eventMetadata.faultingApp}
                    </span>
                  )}
                </h4>
                <div className="flex items-center gap-2 mt-1 text-eims-text-secondary text-xs sm:text-sm">
                  {item.parseMethod?.includes("OCR") ? (
                    <FileImage size={14} className="shrink-0 text-indigo-400" />
                  ) : item.parseMethod?.includes("XML") ? (
                    <Code size={14} className="shrink-0 text-amber-500" />
                  ) : (
                    <FileText size={14} className="shrink-0 text-teal-500" />
                  )}
                  <span className="truncate">{item.parseMethod || "Submitted via Text"}</span>
                </div>
              </div>
              <div className="text-left sm:text-right flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 shrink-0">
                <span className="bg-teal-500/10 border border-teal-500/20 text-teal-600 dark:text-teal-400 text-xs font-medium px-2 py-0.5 rounded">
                  {new Date(item.created_at).toLocaleDateString()}
                </span>
                <div className="flex items-center gap-3 sm:mt-2">
                  <span className="text-xs text-eims-text-muted">By: {item.username}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
                    className="text-eims-text-muted hover:text-rose-400 p-1 transition-colors"
                    title="Delete record"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Detail Modal */}
      {selectedItem && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 sm:p-6 animate-in fade-in duration-200">
          <div 
            ref={modalRef} 
            className="bg-eims-bg border border-eims-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-eims-border bg-eims-surface shrink-0">
              <h2 className="text-lg font-semibold text-eims-text flex items-center gap-2">
                <FileText className="w-5 h-5 text-eims-info dark:text-sky-400" />
                Analysis Record Details
              </h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadMarkdown(selectedItem)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-eims-bg hover:bg-eims-surface-subtle border border-eims-border rounded-lg text-xs font-medium text-eims-text transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export MD
                </button>
                <button
                  onClick={() => downloadPDF(selectedItem)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-eims-accent hover:bg-eims-accent/80 text-white rounded-lg text-xs font-medium transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  Export PDF
                </button>
                <button 
                  onClick={() => setSelectedItem(null)}
                  className="p-2 hover:bg-eims-surface-subtle rounded-full text-eims-text-muted hover:text-eims-text transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            
            {/* Modal Body */}
            <div className="p-6 overflow-y-auto flex-1 bg-eims-bg">
              <AnalysisResultDetail result={selectedItem} onDownloadMD={() => downloadMarkdown(selectedItem)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
