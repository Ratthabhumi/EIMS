import { useState, useEffect, useRef, useMemo } from "react";
import { Search, Trash2, Code, FileImage, FileText, X, Download, ShieldAlert } from "lucide-react";
import { toast } from "react-hot-toast";
import AnalysisResultDetail from "./AnalysisResultDetail";

interface AnalyzerHistoryListProps {
  refreshTrigger?: number;
  className?: string;
  onSearchLatency?: (latencyMs: number) => void;
}

const EVENT_FRIENDLY: Record<string, { title: string; provider: string }> = {
  "4625": { title: "Failed Logon", provider: "Windows Security" },
  "4624": { title: "Successful Logon", provider: "Windows Security" },
  "4740": { title: "Account Lockout", provider: "Windows Security" },
  "4672": { title: "Special Privileges Assigned", provider: "Windows Security" },
  "4688": { title: "Process Creation", provider: "Windows Security" },
  "1102": { title: "Audit Log Cleared", provider: "Windows Security" },
  "4720": { title: "User Account Created", provider: "Windows Security" },
  "2004": { title: "Windows Update Agent", provider: "Windows Update" },
  "1001": { title: "Windows Error", provider: "Windows System" },
  "1000": { title: "App Error", provider: "Windows System" },
  "7045": { title: "Service Installed", provider: "Windows System" },
  "7036": { title: "Service State Change", provider: "Windows System" },
  "7034": { title: "Service Crash", provider: "Windows System" },
  "6008": { title: "Unexpected Shutdown", provider: "Windows System" },
  "41": { title: "Kernel-Power", provider: "Windows System" },
  "5152": { title: "Firewall Block", provider: "Windows Filtering Platform" },
  "1116": { title: "Threat Detected", provider: "Windows Defender" },
};

const INCIDENT_FRIENDLY = {
  title: "Suspicious Authentication Activity",
  provider: "Security / Authentication",
};

// Category operational priorities for ordering catalog entries on empty search
const CATEGORY_PRIORITY: Record<string, number> = {
  "Authentication": 10,
  "Privilege & Authorization": 20,
  "Process & Execution": 30,
  "Services": 40,
  "Firewall & Network Security": 50,
  "Windows Defender & Endpoint Security": 60,
  "PowerShell": 70,
  "System": 80,
  "Account Management": 90,
  "Persistence": 100,
  "RDP & Remote Access": 110,
  "DNS": 120,
  "Active Directory": 130,
  "Group Policy": 140,
  "Audit & Logging": 150,
  "Storage / Disk": 160,
  "Application": 170,
  "Task Scheduler": 180,
  "Networking & File Share": 190,
  "Networking / TCP/IP": 200,
  "Hardware / Resource / Performance": 210,
  "Hyper-V / Virtualization": 220,
  "WMI": 230,
  "DHCP": 240,
  "Backup / Recovery": 250,
};

// Key operational events order at top of catalog
const TOP_EVENT_ORDER: Record<string, number> = {
  "4625": 1,  // Failed Logon
  "4624": 2,  // Successful Logon
  "4740": 3,  // Account Lockout
  "4672": 4,  // Special Privileges Assigned
  "4688": 5,  // Process Creation
  "7045": 6,  // Service Installed
  "5152": 7,  // Firewall Block
  "1116": 8,  // Threat Detected
  "4104": 9,  // PowerShell Script Block
  "41": 10,   // Kernel-Power
  "6008": 11, // Unexpected Shutdown
};

function friendlyLabel(item: any, catalogMap?: Record<string, CatalogEntry>): { title: string; provider: string } {
  const eid = item?.eventId ? String(item.eventId).trim() : "";
  if (eid.toUpperCase().startsWith("AINC-")) return INCIDENT_FRIENDLY;
  if (catalogMap && catalogMap[eid]) {
    return { title: catalogMap[eid].title, provider: catalogMap[eid].provider };
  }
  return EVENT_FRIENDLY[eid] ?? { title: `Event ${eid || item?.provider || "Unknown"}`, provider: item?.provider || "Unknown" };
}

// ── Operational Event Catalog (static knowledge, not analyzed logs) ─────────

interface CatalogEntry {
  event_id: string;
  title: string;
  provider: string;
  category: string;
  severity: string;
  description: string;
  keywords: string[];
  related_events: string[];
  operator_context: string;
  source?: string;
}

const MAX_SEARCH_RESULTS = 15;

function sortCatalogByPriority(entries: CatalogEntry[]): CatalogEntry[] {
  return [...entries].sort((a, b) => {
    const topA = TOP_EVENT_ORDER[a.event_id] ?? 999;
    const topB = TOP_EVENT_ORDER[b.event_id] ?? 999;
    if (topA !== 999 || topB !== 999) return topA - topB;
    const catA = CATEGORY_PRIORITY[a.category] ?? 500;
    const catB = CATEGORY_PRIORITY[b.category] ?? 500;
    if (catA !== catB) return catA - catB;
    return a.event_id.localeCompare(b.event_id, undefined, { numeric: true });
  });
}

function describeCandidate(c: { kind: "history"; record: any } | { kind: "catalog"; record: CatalogEntry }) {
  if (c.kind === "history") {
    const r = c.record;
    const eid = String(r.eventId ?? "").toLowerCase();
    const friendly = friendlyLabel(r);
    const meta = r.eventMetadata || {};
    const inc = meta.incident || {};
    const body = [
      r.description, r.aiSummary, r.parseMethod, r.username,
      inc.name, inc.affectedAsset, inc.classification,
      meta.computer, meta.faultingApp, meta.level, meta.logName,
      Array.isArray(r.solutionSummary?.causes) ? r.solutionSummary.causes.join(" ") : "",
      Array.isArray(r.solutionSummary?.steps) ? r.solutionSummary.steps.join(" ") : "",
      Array.isArray(r.solutionSummary?.evidenceInterpretation) ? r.solutionSummary.evidenceInterpretation.join(" ") : "",
    ].join(" ").toLowerCase();
    return {
      eid, title: friendly.title.toLowerCase(), provider: friendly.provider.toLowerCase(),
      category: "", keywords: "", body, incident: String(inc.name ?? "").toLowerCase(),
      asset: String(inc.affectedAsset ?? "").toLowerCase(),
    };
  }
  const e = c.record;
  return {
    eid: String(e.event_id ?? "").toLowerCase(),
    title: String(e.title ?? "").toLowerCase(),
    provider: String(e.provider ?? "").toLowerCase(),
    category: String(e.category ?? "").toLowerCase(),
    keywords: (e.keywords ?? []).join(" ").toLowerCase(),
    body: `${e.description ?? ""} ${e.operator_context ?? ""} ${(e.related_events ?? []).join(" ")}`.toLowerCase(),
    incident: "", asset: "",
  };
}

function scoreSearch(q: string, c: { kind: "history"; record: any } | { kind: "catalog"; record: CatalogEntry }): number {
  const tokens = q.split(/\s+/).filter(Boolean);
  const d = describeCandidate(c);
  let score = 0;

  // P1 exact event id
  if (q === d.eid) score += 1000;
  // P2 exact title
  if (q === d.title) score += 900;
  // P3 exact provider / category
  if (d.category && q === d.category) score += 800;
  if (q === d.provider) score += 800;
  // P4 exact keyword / alias
  if (d.keywords === q || d.keywords.includes(q)) score += 700;
  // P5 asset / incident context
  if ((d.incident && d.incident.includes(q)) || (d.asset && d.asset.includes(q))) score += 600;
  // P6 description / metadata
  if (d.body.includes(q)) score += 500;

  // token-level relevance (exact field hits weigh more than body hits)
  let allTokensHit = true;
  for (const t of tokens) {
    let ts = 0;
    if (t === d.eid) ts += 300;
    if (d.title === t || d.title.startsWith(t) || d.title.includes(t)) ts += 180;
    if (d.provider === t || d.provider.includes(t)) ts += 120;
    if (d.category && (d.category === t || d.category.includes(t))) ts += 120;
    if (d.keywords.includes(t) || d.keywords.split(" ").some((k) => k === t)) ts += 100;
    if (d.body.includes(t)) ts += 60;
    if (ts === 0) allTokensHit = false;
    score += ts;
  }
  if (allTokensHit && tokens.length > 1) score += 80; // full query coherence
  if (score === 0) {
    score = d.body.includes(q) || d.title.includes(q) ? 40 : 0; // fuzzy floor
  }
  return score;
}

function rankSearch(qRaw: string, historyList: any[], catalog: CatalogEntry[]) {
  const q = qRaw.trim().toLowerCase();
  if (!q) return null;
  const candidates: ({ kind: "history"; record: any } | { kind: "catalog"; record: CatalogEntry })[] = [
    ...historyList.map((record) => ({ kind: "history" as const, record })),
    ...catalog.map((record) => ({ kind: "catalog" as const, record })),
  ];
  const scored = candidates
    .map((c) => ({ c, score: scoreSearch(q, c) }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || a.c.kind.localeCompare(b.c.kind));

  // Dedupe: when a history record and a catalog entry share an event id,
  // keep only the higher-ranked one (history wins on tie) to avoid dupes.
  const seen = new Set<string>();
  const deduped = [];
  for (const s of scored) {
    const eid = (s.c.kind === "history" ? s.c.record.eventId : s.c.record.event_id);
    const key = String(eid ?? "").toUpperCase();
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    deduped.push(s);
  }
  return deduped.slice(0, MAX_SEARCH_RESULTS);
}

export default function AnalyzerHistoryList({
  refreshTrigger = 0,
  className = "",
  onSearchLatency
}: AnalyzerHistoryListProps) {
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
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
      } else {
        console.error(`Failed to fetch history: HTTP ${res.status}`);
      }
    } catch (error) {
      console.error("Failed to fetch history:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCatalog = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/history/catalog");
      if (res.ok) {
        const data = await res.json();
        setCatalog(Array.isArray(data.entries) ? data.entries : []);
      } else {
        console.error(`Failed to fetch catalog: HTTP ${res.status}`);
      }
    } catch (error) {
      console.error("Failed to fetch catalog:", error);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchCatalog();
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

  const catalogMap = useMemo(() => {
    const map: Record<string, CatalogEntry> = {};
    for (const entry of catalog) {
      map[entry.event_id] = entry;
    }
    return map;
  }, [catalog]);

  const sortedCatalog = useMemo(() => {
    return sortCatalogByPriority(catalog);
  }, [catalog]);

  const { ranked, searchLatencyMs } = useMemo(() => {
    if (!searchTerm || !searchTerm.trim()) {
      return { ranked: null, searchLatencyMs: null };
    }
    const t0 = performance.now();
    const res = rankSearch(searchTerm, historyList, catalog);
    const elapsed = Math.max(performance.now() - t0, 0.1);
    return { ranked: res, searchLatencyMs: elapsed };
  }, [searchTerm, historyList, catalog]);

  useEffect(() => {
    if (searchLatencyMs !== null && searchLatencyMs !== undefined) {
      onSearchLatency?.(searchLatencyMs);
    }
  }, [searchLatencyMs, onSearchLatency]);

  // Separate AI demo incident from standard history records
  const { incidentRecord, nonIncidentHistory } = useMemo(() => {
    let incident: any = null;
    const rest: any[] = [];
    for (const h of historyList) {
      if (String(h.eventId).toUpperCase().startsWith("AINC-") && !incident) {
        incident = h;
      } else {
        rest.push(h);
      }
    }
    return { incidentRecord: incident, nonIncidentHistory: rest };
  }, [historyList]);

  // Open detail modal for static operational catalog entries
  const openCatalogItem = (entry: CatalogEntry) => {
    setSelectedItem({
      id: `catalog-${entry.event_id}`,
      eventId: entry.event_id,
      provider: entry.provider,
      parseMethod: "Operational Event Catalog",
      description: entry.description,
      aiSummary: entry.operator_context || entry.description,
      solutionSummary: {
        title: entry.title,
        overview: entry.description,
        causes: entry.operator_context ? [entry.operator_context] : [],
        steps: [
          `Category: ${entry.category}`,
          `Severity: ${entry.severity}`,
          ...(entry.related_events && entry.related_events.length > 0
            ? [`Related Events: ${entry.related_events.join(", ")}`]
            : []),
          ...(entry.keywords && entry.keywords.length > 0
            ? [`Search Keywords: ${entry.keywords.join(", ")}`]
            : []),
        ],
      },
      eventMetadata: {
        level: entry.severity,
        logName: entry.provider,
        timestamp: "Documented Operational Knowledge",
        computer: "Operational Reference Index",
      },
      searchResults: [],
      created_at: new Date().toISOString(),
      username: "Knowledge Base",
      isCatalog: true,
    });
  };

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
    const isInc = String(item.eventId).toUpperCase().startsWith("AINC-");
    const friendly = friendlyLabel(item, catalogMap);
    let content = `# AI Diagnostic Report\n\n`;
    content += `**Event ID:** ${item.eventId}\n`;
    content += `**Title:** ${isInc ? "Suspicious Authentication Activity" : friendly.title}\n`;
    content += `**Provider:** ${isInc ? "Security / Authentication" : item.provider}\n`;
    content += `**Date:** ${item.created_at ? new Date(item.created_at).toLocaleString() : new Date().toLocaleString()}\n\n`;
    if (item.aiSummary) content += `## AI Summary\n\n${item.aiSummary}\n\n`;
    if (item.solutionSummary) {
      content += `## Executive Summary\n${item.solutionSummary.overview || "N/A"}\n\n`;
      content += `## Root Causes / Context\n`;
      (item.solutionSummary.causes || []).forEach((c: string) => { content += `- ${c}\n`; });
      content += `\n## Resolution / Notes\n`;
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

      const isInc = String(item.eventId).toUpperCase().startsWith("AINC-");
      const friendly = friendlyLabel(item, catalogMap);
      const container = document.createElement("div");
      container.style.cssText = "position:fixed;top:-9999px;left:-9999px;width:794px;padding:40px;background:#fff;font-family:Arial,sans-serif;font-size:13px;color:#242321;line-height:1.6;";

      const steps = item.solutionSummary?.steps || [];
      const causes = item.solutionSummary?.causes || [];
      const refs = item.searchResults || [];
      const meta = item.eventMetadata || {};

      container.innerHTML = `
        <h1 style="font-size:20px;font-weight:700;border-bottom:2px solid #68735C;padding-bottom:8px;margin-bottom:12px;">
          Diagnostic Report — ${isInc ? "Suspicious Authentication Activity" : friendly.title} (${item.eventId || "Unknown"})
        </h1>
        <p style="color:#716E66;margin-bottom:20px;">Provider: <strong>${isInc ? "Security / Authentication" : (item.provider || "Unknown")}</strong> &nbsp;|&nbsp; Generated: ${new Date(item.created_at || Date.now()).toLocaleString()}</p>
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
        ${causes.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Root Causes / Context</h2><ul style="padding-left:20px;margin-bottom:12px;">${causes.map((c: string) => `<li style="margin-bottom:4px;">${c}</li>`).join("")}</ul>` : ""}
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

  // ── Unified Row Renderers ──────────────────────────────────────────────────

  const renderIncidentRow = (record: any) => (
    <div
      key={`incident-${record.id || record.eventId}`}
      className="p-4 hover:bg-eims-surface-subtle transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 group cursor-pointer bg-purple-500/[0.02]"
      onClick={() => setSelectedItem(record)}
    >
      <div className="min-w-0 flex-1">
        <h4 className="font-medium text-base sm:text-lg flex flex-wrap items-center gap-2">
          <span className="text-[#9D84B7] dark:text-[#A088BC] group-hover:text-purple-300 transition-colors font-semibold">
            Suspicious Authentication Activity
          </span>
          <span className="bg-purple-500/10 border border-purple-500/20 text-purple-600/85 dark:text-[#B399CE] text-[10px] font-semibold px-2 py-0.5 rounded uppercase tracking-wide shrink-0">
            SYNTHETIC / AI DEMO DATA
          </span>
        </h4>
        <div className="flex items-center gap-2 mt-1 text-eims-text-secondary text-xs sm:text-sm flex-wrap">
          <ShieldAlert size={14} className="shrink-0 text-[#9D84B7] dark:text-[#A088BC]" />
          <span className="font-medium text-eims-text">Security / Authentication</span>
          <span className="text-eims-text-muted">· Incident AINC-2026-0910-0001</span>
          {record.eventMetadata?.incident?.affectedAsset && (
            <span className="bg-eims-surface-subtle text-eims-text-secondary border border-eims-border text-xs px-2 py-0.5 rounded font-mono">
              {record.eventMetadata.incident.affectedAsset}
            </span>
          )}
        </div>
      </div>
      <div className="text-left sm:text-right flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 shrink-0">
        <span className="bg-purple-500/10 border border-purple-500/20 text-purple-600/85 dark:text-[#B399CE] text-xs font-medium px-2 py-0.5 rounded">
          SYNTHETIC AI DEMO
        </span>
        <div className="flex items-center gap-3 sm:mt-2">
          <span className="text-xs text-eims-text-muted">By: {record.username || "AI Investigation"}</span>
        </div>
      </div>
    </div>
  );

  const renderCatalogRow = (entry: CatalogEntry) => (
    <div
      key={`catalog-${entry.event_id}`}
      className="p-4 hover:bg-eims-surface-subtle transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 group cursor-pointer"
      onClick={() => openCatalogItem(entry)}
    >
      <div className="min-w-0 flex-1">
        <h4 className="font-medium text-base sm:text-lg flex flex-wrap items-center gap-2">
          <span className="text-sky-600/90 dark:text-[#7EA8BE] group-hover:text-sky-300 transition-colors">
            {entry.title}
          </span>
          <span className="bg-sky-500/10 border border-sky-500/20 text-sky-600/85 dark:text-sky-400/80 text-[10px] font-medium px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0">
            Catalog
          </span>
        </h4>
        <div className="flex items-center gap-2 mt-1 text-eims-text-secondary text-xs sm:text-sm flex-wrap">
          <FileText size={14} className="shrink-0 text-sky-500/70" />
          <span className="text-eims-text">{entry.provider}</span>
          <span className="text-eims-text-muted">· Event {entry.event_id}</span>
          <span className="text-eims-text-muted text-xs hidden md:inline">({entry.category} · {entry.severity})</span>
        </div>
        <p className="mt-1 text-xs text-eims-text-muted line-clamp-1">{entry.description}</p>
      </div>
      <div className="text-left sm:text-right flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 shrink-0">
        <span className="bg-sky-500/10 border border-sky-500/20 text-sky-600/85 dark:text-sky-400/80 text-xs font-medium px-2 py-0.5 rounded">
          Knowledge Base
        </span>
        <span className="text-xs text-eims-text-muted sm:mt-2 hidden sm:block">Reference Index</span>
      </div>
    </div>
  );

  const renderHistoryRow = (record: any) => {
    const friendly = friendlyLabel(record, catalogMap);
    return (
      <div
        key={`history-${record.id}`}
        className="p-4 hover:bg-eims-surface-subtle transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 group cursor-pointer"
        onClick={() => setSelectedItem(record)}
      >
        <div className="min-w-0 flex-1">
          <h4 className="font-medium text-base sm:text-lg flex flex-wrap items-center gap-2">
            <span className="text-emerald-600/90 dark:text-[#78B096] group-hover:text-emerald-300 transition-colors">
              {friendly.title}
            </span>
            <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-600/85 dark:text-[#78B096] text-[10px] font-medium px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0">
              Analyzed Log
            </span>
            {record.eventMetadata?.faultingApp && (
              <span className="bg-eims-surface-subtle text-eims-text-secondary border border-eims-border text-xs px-2 py-0.5 rounded truncate max-w-full font-mono">
                {record.eventMetadata.faultingApp}
              </span>
            )}
          </h4>
          <div className="flex items-center gap-2 mt-1 text-eims-text-secondary text-xs sm:text-sm flex-wrap">
            {record.parseMethod?.includes("OCR") ? (
              <FileImage size={14} className="shrink-0 text-indigo-400/80" />
            ) : record.parseMethod?.includes("XML") ? (
              <Code size={14} className="shrink-0 text-amber-500/80" />
            ) : (
              <FileText size={14} className="shrink-0 text-emerald-500/70" />
            )}
            <span className="text-eims-text">{friendly.provider}</span>
            <span className="text-eims-text-muted">· Event {record.eventId}</span>
            <span className="text-eims-text-muted text-xs">({record.parseMethod || "Submitted via Text"})</span>
          </div>
        </div>
        <div className="text-left sm:text-right flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 shrink-0">
          <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-600/85 dark:text-[#78B096] text-xs font-medium px-2 py-0.5 rounded">
            {new Date(record.created_at).toLocaleDateString()}
          </span>
          <div className="flex items-center gap-3 sm:mt-2">
            <span className="text-xs text-eims-text-muted">By: {record.username}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(record.id);
              }}
              className="text-eims-text-muted hover:text-rose-400 p-1 transition-colors"
              title="Delete record"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`bg-eims-surface border border-eims-border rounded-xl shadow-sm overflow-hidden flex flex-col ${className}`}>
      {/* Search Header */}
      <div className="p-4 border-b border-eims-border flex items-center justify-between bg-eims-bg/50 shrink-0">
        <div className="relative w-full max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-eims-text-muted" />
          <input
            type="text"
            placeholder="Search Event ID, title, provider, keyword..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-eims-bg border border-eims-border rounded-lg text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-accent transition-colors"
          />
        </div>
        <div className="text-xs text-eims-text-muted font-medium ml-4 shrink-0 hidden sm:block">
          {searchTerm.trim().length > 0 ? (
            <span>
              Top {ranked?.length || 0} Results
              {searchLatencyMs !== null && (
                <span className="ml-1.5 text-[10px] text-teal-600 dark:text-[#78B096]">
                  ({searchLatencyMs < 1 ? searchLatencyMs.toFixed(1) : Math.round(searchLatencyMs)}ms)
                </span>
              )}
            </span>
          ) : (
            `Operational Catalog: ${catalog.length} events`
          )}
        </div>
      </div>

      {/* Unified Scrollable Result List */}
      <div className="divide-y divide-eims-border flex-1 min-h-0 overflow-y-auto">
        {isLoading ? (
          <div className="p-8 text-center text-eims-text-muted">Loading history and catalog...</div>
        ) : searchTerm.trim().length > 0 ? (
          /* ACTIVE SEARCH: TOP 15 RANKED RESULTS */
          ranked && ranked.length === 0 ? (
            <div className="p-8 text-center text-eims-text-muted">No matching records or catalog entries found.</div>
          ) : ranked ? (
            <>
              <div className="px-4 pt-3 pb-1 text-xs text-eims-text-muted font-medium bg-eims-bg/30">
                Showing top {ranked.length} ranking results for "{searchTerm.trim()}"
              </div>
              {ranked.map(({ c }) => {
                if (c.kind === "history") {
                  if (String(c.record.eventId).toUpperCase().startsWith("AINC-")) {
                    return renderIncidentRow(c.record);
                  }
                  return renderHistoryRow(c.record);
                }
                return renderCatalogRow(c.record);
              })}
            </>
          ) : (
            <div className="p-8 text-center text-eims-text-muted">No records found.</div>
          )
        ) : (
          /* NO SEARCH: FULL OPERATIONAL EVENT CATALOG (141) + AI INCIDENT + REAL HISTORY */
          <>
            {/* 1. Suspicious Authentication Activity [SYNTHETIC AI DEMO] */}
            {incidentRecord && renderIncidentRow(incidentRecord)}

            {/* 2. Operational Event Catalog (Complete 141 entries sorted by priority) */}
            {sortedCatalog.map((entry) => renderCatalogRow(entry))}

            {/* 3. Actual analyzed history records */}
            {nonIncidentHistory.map((item) => renderHistoryRow(item))}
          </>
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
                {String(selectedItem.eventId).toUpperCase().startsWith("AINC-") ? (
                  <>
                    <ShieldAlert className="w-5 h-5 text-[#A088BC]" />
                    <span>AI Incident Investigation — Suspicious Authentication Activity</span>
                  </>
                ) : selectedItem.isCatalog ? (
                  <>
                    <FileText className="w-5 h-5 text-sky-500/80 dark:text-[#7EA8BE]" />
                    <span>Operational Knowledge Base — Event {selectedItem.eventId}</span>
                  </>
                ) : (
                  <>
                    <FileText className="w-5 h-5 text-emerald-500/80 dark:text-[#78B096]" />
                    <span>Analysis Record Details — Event {selectedItem.eventId}</span>
                  </>
                )}
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
