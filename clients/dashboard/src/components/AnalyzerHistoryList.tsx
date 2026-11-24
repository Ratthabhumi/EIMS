import { escapeReportData } from '@/lib/report-data';
import { useState, useEffect, useRef, useMemo } from "react";
import { Search, Trash2, Code, FileImage, FileText, X, Download, ShieldAlert } from "lucide-react";
import { toast } from "react-hot-toast";
import AnalysisResultDetail from "./AnalysisResultDetail";
import EventIncidentLink from "./incidents/EventIncidentLink";
import IncidentWorkspace from "./incidents/IncidentWorkspace";
import { apiUrl } from "@/lib/api";
import { knowledgeMatchHtml, knowledgeMatchMarkdown } from "./KnowledgeMatchBadge";
import { downloadHtmlAsPdf, preloadPdfExport } from "@/lib/pdf-export";
import { readPortalPreferences, writePortalPreferences, type HistorySort } from "@/lib/portal-preferences";

export type AnalyzerMainTab = "history" | "catalog" | "incident";

interface AnalyzerHistoryListProps {
  refreshTrigger?: number;
  className?: string;
  onSearchLatency?: (latencyMs: number) => void;
  /** Switch to Incident Workspace tab with this incident (no drawer). */
  onOpenIncident?: (incidentId: string, analysisHistoryId?: number) => void;
  /** Close selected incident detail → Incident list landing (stay on Incident tab). */
  onCloseIncident?: () => void;
  /** Prefer selecting this analysis_history.id when history loads (deep link). */
  initialAnalysisId?: number | null;
  /** Optional known asset_id for Incident Core correlation (from URL/query; never invent). */
  correlationAssetId?: string | null;
  /** Selected incident for the Incident Workspace tab. */
  incidentId?: string | null;
  /** Controlled main tab; when omitted the list owns the tab locally. */
  activeTab?: AnalyzerMainTab;
  onActiveTabChange?: (tab: AnalyzerMainTab) => void;
  /** Analyzer report output language (not Portal UI language). */
  analysisLanguage?: "th" | "en";
  onIncidentChanged?: (incidentId: string) => void;
}

const HISTORY_PAGE_SIZE = 50;

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

function isSyntheticDemo(item: any): boolean {
  return String(item?.eventId ?? "").toUpperCase() === "AINC-2026-0910-0001";
}

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
  if (isSyntheticDemo(item)) return INCIDENT_FRIENDLY;
  const meta = item?.eventMetadata ?? {};
  const family = meta.sourceFamily || (/windows|^security$|grouppolicy|kernel-power|eventlog|distributedcom|service control manager/i.test(item?.provider ?? "") ? "windows_event" : "unknown_text");
  const code = meta.diagnosticCode || eid;
  const defaultKinds: Record<string, string> = {windows_event:"official_event_id", veeam_vbr:"eims_diagnostic", vmware:"eims_diagnostic", fortinet:"log_category", cisco_asa:"official_message_id", palo_alto:"log_category", linux_syslog:"general_signature"};
  const kind = meta.attributes?.codeType || defaultKinds[family];
  const entry = catalogMap?.[`${family}:${kind}:${code}`];
  if (entry && (family !== "cisco_asa" || meta.attributes?.deviceType === "ASA")) {
    return { title: entry.title, provider: item?.provider || entry.provider };
  }
  return (family === "windows_event" ? EVENT_FRIENDLY[eid] : undefined) ?? { title: `Record ${eid || item?.provider || "Unknown"}`, provider: item?.provider || "Unknown" };
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
  catalog_id: string;
  source_family: string;
  vendor: string;
  product: string;
  code_type: string;
  diagnostic_code: string;
  support_level: string;
  verification_status: string;
  investigation_steps?: string[];
  official_references?: { title: string; url: string; scope: string }[];
  compatibility_scope?: string;
  knowledge_class?: string;
  lifecycle_status?: string;
  cert_class?: string;
  parser_linkage?: string;
  analyzer_availability?: "matchable" | "not_matchable" | string;
  eligibility?: string | null;
  human_approval?: string | null;
}

type CatalogTotals = {
  governed_records: number;
  analyzer_matchable: number;
  other_governed: number;
  cert_class_b: number;
  eligible: number;
  blocked: number;
  ineligible: number;
  human_approved: number;
};

type CatalogFacet = "all" | "matchable" | "class_b" | "eligible";

function catalogTrustLabel(entry: CatalogEntry): string {
  const bits: string[] = [];
  if (entry.analyzer_availability === "matchable") bits.push("Analyzer-matchable");
  else if (entry.analyzer_availability === "not_matchable") bits.push("Not Analyzer-matchable");
  if (entry.cert_class) bits.push(`Class ${entry.cert_class}`);
  if (entry.eligibility) bits.push(entry.eligibility);
  if (entry.knowledge_class === "diagnostic_candidate" || entry.lifecycle_status === "candidate") {
    bits.push("not approved");
  } else if (entry.verification_status === "official_documentation_verified") {
    bits.push("Documented reference");
  } else if (entry.verification_status === "preserved_legacy") {
    bits.push("Operational context");
  }
  return bits.length ? bits.join(" · ") : (entry.verification_status || "Review status not provided");
}

function isCatalogCandidate(entry: CatalogEntry): boolean {
  return entry.knowledge_class === "diagnostic_candidate" || entry.lifecycle_status === "candidate";
}

const SOURCE_LABELS: Record<string, string> = {
  windows_event: "Microsoft Windows", veeam_vbr: "Veeam", vmware: "VMware",
  fortinet: "Fortinet", cisco_asa: "Cisco ASA / FTD", palo_alto: "Palo Alto PAN-OS",
  linux_syslog: "Linux / OpenSSH", json: "Structured JSON (parser only)",
};
const CODE_LABELS: Record<string, string> = {
  official_event_id: "Official Event ID", official_message_id: "Official Message ID",
  eims_diagnostic: "EIMS diagnostic", log_category: "Log category", general_signature: "Diagnostic signature",
};

const MAX_SEARCH_RESULTS = 15;

function sortCatalogByPriority(entries: CatalogEntry[]): CatalogEntry[] {
  return [...entries].sort((a, b) => {
    const productOrder = a.product.localeCompare(b.product);
    if (productOrder) return productOrder;
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
      r.description, r.aiSummary, r.parseMethod, r.username, r.provider,
      isSyntheticDemo(r) ? "Synthetic Demo" : "",
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
    provider: `${e.provider ?? ""} ${e.vendor} ${e.product} ${e.source_family}`.toLowerCase(),
    category: String(e.category ?? "").toLowerCase(),
    keywords: (e.keywords ?? []).join(" ").toLowerCase(),
    body: `${e.description ?? ""} ${e.operator_context ?? ""} ${e.code_type} ${(e.investigation_steps ?? []).join(" ")} ${(e.related_events ?? []).join(" ")}`.toLowerCase(),
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

  return scored.slice(0, MAX_SEARCH_RESULTS);
}

type OpenIncidentRow = { incident_id: string; title: string; status: string; severity: string };

export default function AnalyzerHistoryList({
  refreshTrigger = 0,
  className = "",
  onOpenIncident,
  onCloseIncident,
  initialAnalysisId = null,
  correlationAssetId = null,
  incidentId = null,
  activeTab: controlledTab,
  onActiveTabChange,
  analysisLanguage = "en",
  onIncidentChanged,
}: AnalyzerHistoryListProps) {
  // onSearchLatency omitted: ranking stays pure; host may still pass the prop.
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [catalogTotals, setCatalogTotals] = useState<CatalogTotals | null>(null);
  const [catalogFacet, setCatalogFacet] = useState<CatalogFacet>("matchable");
  // Product-family counts always describe the Analyzer-matchable subset (181), not full 911.
  const [analyzerFamilyCounts, setAnalyzerFamilyCounts] = useState<Record<string, number>>({});
  const [sourceFilter, setSourceFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(false);
  const [nextHistoryOffset, setNextHistoryOffset] = useState(0);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [localTab, setLocalTab] = useState<AnalyzerMainTab>("history");
  const activeTab = controlledTab ?? localTab;
  const setActiveTab = (tab: AnalyzerMainTab) => {
    if (controlledTab === undefined) setLocalTab(tab);
    onActiveTabChange?.(tab);
  };
  const [historyOrder, setHistoryOrder] = useState<HistorySort>("newest");
  const [selectedItem, setSelectedItem] = useState<any | null>(null);
  const [openIncidents, setOpenIncidents] = useState<OpenIncidentRow[]>([]);
  const [openIncidentsLoaded, setOpenIncidentsLoaded] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const appliedInitialAnalysis = useRef(false);

  useEffect(() => {
    setHistoryOrder(readPortalPreferences().historySort);
  }, []);

  useEffect(() => {
    if (activeTab !== "incident") return;
    let cancelled = false;
    // refreshTrigger re-fetches after association without a separate setState gate effect.
    void fetch(apiUrl("/api/v1/incidents?limit=50"), { cache: "no-store" })
      .then((r) => r.json())
      .then((body) => {
        if (cancelled) return;
        const rows = Array.isArray(body?.data) ? body.data : [];
        setOpenIncidents(
          rows
            .filter((i: OpenIncidentRow) => !["resolved", "closed"].includes(String(i.status)))
            .map((i: OpenIncidentRow) => ({
              incident_id: i.incident_id,
              title: i.title,
              status: i.status,
              severity: i.severity,
            })),
        );
        setOpenIncidentsLoaded(true);
      })
      .catch(() => {
        if (!cancelled) setOpenIncidentsLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, refreshTrigger]);

  useEffect(() => {
    if (selectedItem) {
      void preloadPdfExport().catch((error) => console.warn("PDF export preload failed", error));
    }
  }, [selectedItem]);

  const handleLoadMoreHistory = async () => {
    if (isLoadingMore || !hasMoreHistory) return;
    setIsLoadingMore(true);
    try {
      const data = await requestHistoryPage(nextHistoryOffset);
      setHistoryList((previous) => [...previous, ...data]);
      setNextHistoryOffset((previous) => previous + data.length);
      setHasMoreHistory(data.length === HISTORY_PAGE_SIZE);
    } catch (error) {
      console.error("Failed to load older history:", error);
      toast.error("Failed to load older history records.");
    } finally {
      setIsLoadingMore(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    void requestHistoryPage(0)
      .then((data) => {
        if (cancelled) return;
        setHistoryList(data);
        setNextHistoryOffset(data.length);
        setHasMoreHistory(data.length === HISTORY_PAGE_SIZE);
        if (
          !appliedInitialAnalysis.current &&
          initialAnalysisId != null &&
          Number.isFinite(initialAnalysisId) &&
          (controlledTab ?? localTab) !== "incident"
        ) {
          const match = data.find((row: { id?: number }) => row.id === initialAnalysisId);
          if (match) {
            appliedInitialAnalysis.current = true;
            setSelectedItem(match);
            setActiveTab("history");
          }
        }
      })
      .catch((error) => console.error("Failed to fetch history:", error))
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, [refreshTrigger, initialAnalysisId]);

  useEffect(() => {
    if (activeTab !== "catalog") return;
    let cancelled = false;
    setIsLoadingCatalog(true);
    void requestUnifiedCatalog(catalogFacet)
      .then((payload) => {
        if (!cancelled) {
          setCatalog(payload.records);
          setCatalogTotals(payload.totals);
          setCatalogLoaded(true);
          if (catalogFacet === "matchable") {
            const counts: Record<string, number> = {};
            for (const entry of payload.records) {
              const family = entry.source_family || "";
              if (!family) continue;
              counts[family] = (counts[family] || 0) + 1;
            }
            setAnalyzerFamilyCounts(counts);
          }
        }
      })
      .catch((error) => console.error("Failed to fetch unified catalog:", error))
      .finally(() => {
        if (!cancelled) setIsLoadingCatalog(false);
      });
    return () => { cancelled = true; };
  }, [activeTab, catalogFacet]);

  useEffect(() => {
    if (sourceFilter === "all") return;
    if ((analyzerFamilyCounts[sourceFilter] ?? 0) > 0) return;
    setSourceFilter("all");
  }, [sourceFilter, analyzerFamilyCounts]);

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this record?")) return;
    
    const loadingToast = toast.loading("Deleting...");
    try {
      const res = await fetch(apiUrl(`/api/v1/history/${id}`), {
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
      map[entry.catalog_id] = entry;
    }
    return map;
  }, [catalog]);

  const filteredCatalog = useMemo(() => catalog.filter(entry => sourceFilter === "all" || entry.source_family === sourceFilter), [catalog, sourceFilter]);
  const sortedCatalog = useMemo(() => sortCatalogByPriority(filteredCatalog), [filteredCatalog]);

  const sortedHistory = useMemo(() => {
    const timestamp = (record: any) => {
      const value = Date.parse(record.created_at ?? "");
      return Number.isFinite(value) ? value : 0;
    };
    const direction = historyOrder === "newest" ? -1 : 1;
    return [...historyList].sort((a, b) => direction * (
      timestamp(a) - timestamp(b) ||
      String(a.id).localeCompare(String(b.id), "en", { numeric: true })
    ));
  }, [historyList, historyOrder]);

  // Keep ranking pure during render (no performance.now). Latency is optional UX only.
  const { visibleHistory, ranked } = useMemo(() => {
    if (!searchTerm || !searchTerm.trim()) {
      return { visibleHistory: sortedHistory, ranked: null };
    }
    const q = searchTerm.trim().toLowerCase();
    // History retains chronological order and every matching analysis,
    // including multiple analyses of the same event ID.
    const matches = activeTab === "history"
      ? sortedHistory.filter(record => scoreSearch(q, { kind: "history", record }) > 0)
      : [];
    const res = activeTab === "catalog" ? rankSearch(searchTerm, [], filteredCatalog) : null;
    return { visibleHistory: matches, ranked: res };
  }, [searchTerm, sortedHistory, filteredCatalog, activeTab]);

  // Search latency is optional UX; omit impure timing during render/effects.

  // Open detail modal for static operational catalog entries
  const openCatalogItem = (entry: CatalogEntry) => {
    setSelectedItem({
      id: `catalog-${entry.catalog_id}`,
      eventId: entry.event_id,
      provider: entry.provider,
      parseMethod: "Diagnostic Knowledge Catalog",
      description: entry.description,
      aiSummary: entry.operator_context || entry.description,
      solutionSummary: {
        title: entry.title,
        overview: entry.description,
        causes: entry.operator_context ? [entry.operator_context] : [],
        steps: [
          "This catalog entry is reference context. It does not by itself confirm a root cause.",
          `Trust/review status from API: ${entry.verification_status || "not provided"}`,
          `Support level: ${entry.support_level || "not provided"}`,
          `Product: ${entry.product}`,
          `${CODE_LABELS[entry.code_type] || entry.code_type}: ${entry.diagnostic_code}`,
          `Scope: ${entry.compatibility_scope || "Not specified"}`,
          ...(entry.investigation_steps || []),
          `Category: ${entry.category}`,
          `Severity context: ${entry.severity}`,
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
        timestamp: "Catalog reference (not an observed event time)",
        computer: "Diagnostic Knowledge Catalog",
      },
      searchResults: (entry.official_references || []).map(ref => ({ title: ref.title, link: ref.url, snippet: ref.scope, sourceType: "official" })),
      created_at: new Date().toISOString(),
      username: "Knowledge Catalog",
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
    const isInc = isSyntheticDemo(item);
    const friendly = friendlyLabel(item, catalogMap);
    let content = `# AI Diagnostic Report\n\n`;
    content += `**Event ID:** ${item.eventId || "Not provided"}\n`;
    if (item.eventMetadata?.diagnosticCode) content += `**Diagnostic Code:** ${item.eventMetadata.diagnosticCode}\n`;
    content += `**Title:** ${isInc ? "Suspicious Authentication Activity" : friendly.title}\n`;
    content += `**Provider:** ${isInc ? "Security / Authentication" : (item.provider || "Not provided")}\n`;
    content += `**Saved:** ${item.created_at ? new Date(item.created_at).toLocaleString() : "Not provided"}\n`;
    content += knowledgeMatchMarkdown(item.solutionSummary?.knowledgeMatch) + "\n";
    if (item.aiSummary) content += `## AI Summary\n\n${item.aiSummary}\n\n`;
    if (item.solutionSummary) {
      content += `## Executive Summary\n${item.solutionSummary.overview || "N/A"}\n\n`;
      content += `## Possible Causes / Assessment\n`;
      (item.solutionSummary.causes || []).forEach((c: string) => { content += `- ${c}\n`; });
      content += `\n## Recommended Next Steps\n`;
      (item.solutionSummary.steps || []).forEach((s: string) => { content += `${s}\n`; });
      if (item.solutionSummary.evidence && item.solutionSummary.evidence.length > 0) {
        content += `\n## Observed Evidence\n`;
        item.solutionSummary.evidence.forEach((e: string) => { content += `- ${e}\n`; });
        if (item.solutionSummary.confidence) content += `\nConfidence: ${item.solutionSummary.confidence}\n`;
      }
      if (item.solutionSummary.evidenceItems?.length) {
        content += `\n## Extracted Source Evidence\n`;
        item.solutionSummary.evidenceItems.forEach((e: any) => {
          content += `- ${e.sourceFile || "Not provided"}:${e.lineNumber ?? "Not provided"} — ${e.message || "Not provided"}\n`;
        });
      }
      if (item.solutionSummary.limitations && item.solutionSummary.limitations.length > 0) {
        content += `\n## What Is Still Unknown\n`;
        item.solutionSummary.limitations.forEach((u: string) => { content += `- ${u}\n`; });
      }
      if (item.solutionSummary.nextEvidence && item.solutionSummary.nextEvidence.length > 0) {
        content += `\n## Next Evidence to Collect\n`;
        item.solutionSummary.nextEvidence.forEach((n: string) => { content += `- ${n}\n`; });
      }
    }
    if (item.searchResults && item.searchResults.length > 0) {
      content += `\n## References\n`;
      item.searchResults.forEach((r: any) => { content += `- [${r.title}](${r.link})${r.sourceType && r.sourceType !== "official" ? " (community)" : ""}\n`; });
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
    const safeItem = escapeReportData(item);
    if (!safeItem) return;
    const toastId = toast.loading("Generating PDF...");
    try {
      const isInc = isSyntheticDemo(safeItem);
      const friendly = friendlyLabel(safeItem, catalogMap);
      const container = document.createElement("div");
      container.dataset.eimsPdfExport = "true";
      container.style.cssText = "position:fixed;top:0;left:0;width:794px;padding:40px;background:#fff;font-family:Arial,sans-serif;font-size:13px;color:#242321;line-height:1.6;opacity:0;pointer-events:none;z-index:-1;";

      const steps = safeItem.solutionSummary?.steps || [];
      const causes = safeItem.solutionSummary?.causes || [];
      const refs = safeItem.searchResults || [];
      const meta = safeItem.eventMetadata || {};
      const evList: string[] = safeItem.solutionSummary?.evidence || [];
      const unknowns: string[] = safeItem.solutionSummary?.limitations || [];
      const nextEv: string[] = safeItem.solutionSummary?.nextEvidence || [];
      const conf: string = safeItem.solutionSummary?.confidence || "";

      container.innerHTML = `
        <h1 style="font-size:20px;font-weight:700;border-bottom:2px solid #68735C;padding-bottom:8px;margin-bottom:12px;">
          Diagnostic Report — ${isInc ? "Suspicious Authentication Activity" : friendly.title} (${safeItem.eventId || "Unknown"})
        </h1>
        <p style="color:#716E66;margin-bottom:20px;">Provider: <strong>${isInc ? "Security / Authentication" : (safeItem.provider || "Unknown")}</strong> &nbsp;|&nbsp; Saved: ${safeItem.created_at ? new Date(safeItem.created_at).toLocaleString() : "Not provided"}</p>
        ${meta.diagnosticCode ? `<p>Diagnostic Code: ${meta.diagnosticCode}</p>` : ""}
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Event Metadata</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          <div><span style="color:#716E66;font-size:11px;">Level</span><br/><strong>${meta.level || "Not provided"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Log Name</span><br/><strong>${meta.logName || "Not provided"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Time</span><br/><strong>${meta.timestamp || "Not provided"}</strong></div>
          <div><span style="color:#716E66;font-size:11px;">Computer</span><br/><strong>${meta.computer || "Not provided"}</strong></div>
          ${meta.faultingApp ? `<div style="grid-column:1/-1"><span style="color:#716E66;font-size:11px;">Faulting App</span><br/><strong style="color:#dc2626;">${meta.faultingApp}</strong></div>` : ""}
        </div>
        ${knowledgeMatchHtml(safeItem.solutionSummary?.knowledgeMatch)}
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Summary</h2>
        <div style="background:#F5F3EE;padding:12px 16px;border-radius:8px;margin-bottom:12px;">${safeItem.solutionSummary?.overview || safeItem.aiSummary || "No summary available."}</div>
        ${causes.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Possible Causes / Assessment</h2><ul style="padding-left:20px;margin-bottom:12px;">${causes.map((c: string) => `<li style="margin-bottom:4px;">${c}</li>`).join("")}</ul>` : ""}
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Recommended Next Steps</h2>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;padding:12px 16px;border-radius:8px;margin-bottom:12px;">
          ${steps.length > 0 ? `<ol style="padding-left:20px;margin:0;">${steps.map((s: string) => `<li style="margin-bottom:6px;">${s}</li>`).join("")}</ol>` : "<p>No specific steps provided.</p>"}
        </div>
        ${evList.length > 0 ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Observed Evidence${conf ? ` (confidence: ${conf})` : ""}</h2><ul style="padding-left:20px;margin-bottom:12px;">${evList.map((e: string) => `<li style="margin-bottom:4px;">${e}</li>`).join("")}</ul>` : ""}
        ${safeItem.solutionSummary?.evidenceItems?.length ? `<h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Extracted Source Evidence</h2><ul>${safeItem.solutionSummary.evidenceItems.map((e: any) => `<li>${e.sourceFile || "Not provided"}:${e.lineNumber ?? "Not provided"} — ${e.message || "Not provided"}</li>`).join("")}</ul>` : ""}
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
          `Diagnostic_Report_${safeItem.eventId || "Unknown"}.pdf`,
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

  // ── Unified Row Renderers ──────────────────────────────────────────────────

  const renderCatalogRow = (entry: CatalogEntry) => (
    <div
      key={`catalog-${entry.catalog_id}`}
      className="p-4 hover:bg-eims-surface-subtle transition-colors flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 group cursor-pointer"
      onClick={() => openCatalogItem(entry)}
    >
      <div className="min-w-0 flex-1">
        <h4 className="font-medium text-base sm:text-lg flex flex-wrap items-center gap-2">
          <span className="text-sky-600/90 dark:text-[#7EA8BE] group-hover:text-sky-300 transition-colors">
            {entry.title}
          </span>
          <span className="bg-sky-500/10 border border-sky-500/20 text-sky-600/85 dark:text-sky-400/80 text-[10px] font-medium px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0">
            {isCatalogCandidate(entry) ? "Candidate" : "Reference"}
          </span>
        </h4>
        <div className="flex items-center gap-2 mt-1 text-eims-text-secondary text-xs sm:text-sm flex-wrap">
          <FileText size={14} className="shrink-0 text-sky-500/70" />
          <span className="text-eims-text">{entry.provider}</span>
          <span className="text-eims-text-muted">· {CODE_LABELS[entry.code_type] || entry.code_type}: {entry.diagnostic_code}</span>
          <span className="text-eims-text-muted text-xs hidden md:inline">({entry.category} · {entry.severity})</span>
        </div>
        <p className="mt-1 text-xs text-eims-text-muted line-clamp-1">{entry.description}</p>
      </div>
      <div className="text-left sm:text-right flex sm:flex-col items-center sm:items-end justify-between w-full sm:w-auto gap-2 shrink-0">
        <span className="bg-sky-500/10 border border-sky-500/20 text-sky-600/85 dark:text-sky-400/80 text-xs font-medium px-2 py-0.5 rounded">
          {catalogTrustLabel(entry)}
        </span>
        <span className="text-xs text-eims-text-muted sm:mt-2 hidden sm:block">Not a confirmed root cause</span>
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
              {isSyntheticDemo(record) ? "Synthetic Demo" : "Analyzed Log"}
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

  const openFromDetail = (nextIncidentId: string, analysisId?: number) => {
    setSelectedItem(null);
    onOpenIncident?.(nextIncidentId, analysisId);
  };

  const tabBtn = (tab: AnalyzerMainTab, id: string, label: string) => (
    <button
      type="button"
      role="tab"
      id={id}
      aria-selected={activeTab === tab}
      aria-controls="analyzer-records-panel"
      onClick={() => {
        setActiveTab(tab);
        if (tab === "catalog" && !catalogLoaded) setIsLoadingCatalog(true);
      }}
      className={`px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap ${
        activeTab === tab ? "bg-eims-accent text-white" : "bg-eims-bg text-eims-text-secondary hover:bg-eims-surface-subtle"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className={`bg-eims-surface border border-eims-border rounded-xl shadow-sm overflow-hidden flex flex-col ${className}`} data-testid="analyzer-main-tabs">
      <div className="p-4 border-b border-eims-border bg-eims-bg/50 shrink-0 space-y-3">
        <div role="tablist" aria-label="Analyzer main content" className="flex flex-wrap gap-2">
          {tabBtn("history", "analysis-history-tab", "Analysis History")}
          {tabBtn(
            "catalog",
            "event-catalog-tab",
            `Knowledge Catalog${catalogTotals ? ` (${catalogTotals.governed_records})` : catalogLoaded ? ` (${catalog.length})` : ""}`,
          )}
          {tabBtn("incident", "incident-workspace-tab", "Incident Workspace")}
        </div>
        {activeTab !== "incident" ? (
          <>
            <p className="text-xs text-eims-text-muted">
              {activeTab === "history"
                ? `${historyList.length} analysis records · Sorted by analysis date`
                : catalogLoaded && catalogTotals
                  ? `Showing ${catalog.length} of ${catalogTotals.governed_records} · Matchable ${catalogTotals.analyzer_matchable} · Class B ${catalogTotals.cert_class_b} · Eligible ${catalogTotals.eligible}`
                  : catalogLoaded
                    ? `${catalog.length} catalog records`
                  : "Loading catalog inventory…"}
            </p>
            {activeTab === "catalog" && catalogTotals && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs" data-testid="unified-catalog-kpis">
                <div className="rounded-lg border border-eims-border bg-eims-bg px-2 py-1.5">
                  <div className="text-eims-text-muted">Governed</div>
                  <div className="font-semibold text-eims-text">{catalogTotals.governed_records}</div>
                </div>
                <div className="rounded-lg border border-eims-border bg-eims-bg px-2 py-1.5">
                  <div className="text-eims-text-muted">Analyzer-matchable</div>
                  <div className="font-semibold text-eims-text">{catalogTotals.analyzer_matchable}</div>
                </div>
                <div className="rounded-lg border border-eims-border bg-eims-bg px-2 py-1.5">
                  <div className="text-eims-text-muted">Other governed inventory</div>
                  <div className="font-semibold text-eims-text">{catalogTotals.other_governed}</div>
                </div>
                <div className="rounded-lg border border-eims-border bg-eims-bg px-2 py-1.5">
                  <div className="text-eims-text-muted">Eligible</div>
                  <div className="font-semibold text-eims-text">{catalogTotals.eligible}</div>
                </div>
              </div>
            )}
            {activeTab === "catalog" && (
              <div className="flex flex-wrap gap-2" role="group" aria-label="Catalog facets">
                {(
                  [
                    ["matchable", "Analyzer-matchable"],
                    ["all", "All governed"],
                    ["class_b", "Class B"],
                    ["eligible", "Eligible"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setCatalogFacet(id)}
                    className={`px-2 py-1 text-xs rounded-lg border ${
                      catalogFacet === id
                        ? "border-eims-accent bg-eims-accent/10 text-eims-text"
                        : "border-eims-border text-eims-text-muted"
                    }`}
                  >
                    {label}
                    {catalogTotals
                      ? ` (${
                          id === "matchable"
                            ? catalogTotals.analyzer_matchable
                            : id === "all"
                              ? catalogTotals.governed_records
                              : id === "class_b"
                                ? catalogTotals.cert_class_b
                                : catalogTotals.eligible
                        })`
                      : ""}
                  </button>
                ))}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative flex-1 min-w-0">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-eims-text-muted" />
                <input
                  type="text"
                  aria-label={activeTab === "history" ? "Search analysis history" : "Search event catalog"}
                  placeholder="Search Event ID, title, provider, keyword..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm bg-eims-bg border border-eims-border rounded-lg text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-accent transition-colors"
                />
              </div>
              {activeTab === "history" && (
                <select
                  aria-label="History sort order"
                  value={historyOrder}
                  onChange={(e) => {
                    const next = e.target.value as HistorySort;
                    setHistoryOrder(next);
                    writePortalPreferences({ historySort: next });
                  }}
                  className="px-2 py-2 text-sm bg-eims-bg border border-eims-border rounded-lg text-eims-text"
                >
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                </select>
              )}
              {activeTab === "catalog" && (
                <select
                  aria-label="Analyzer product family filter"
                  data-testid="analyzer-product-family-filter"
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="min-w-0 sm:max-w-xs max-w-full px-2 py-2 text-sm bg-eims-bg border border-eims-border rounded-lg text-eims-text"
                >
                  <option value="all">
                    All Analyzer products ({catalogTotals?.analyzer_matchable ?? "…"})
                  </option>
                  {Object.entries(SOURCE_LABELS)
                    .map(([family, label]) => ({
                      family,
                      label,
                      count: analyzerFamilyCounts[family] ?? 0,
                    }))
                    .filter((row) => row.count > 0)
                    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
                    .map(({ family, label, count }) => (
                      <option key={family} value={family}>
                        {label} ({count})
                      </option>
                    ))}
                </select>
              )}
            </div>
            {searchTerm.trim() && (
              <p className="text-xs text-eims-text-muted">
                {activeTab === "history"
                  ? `${visibleHistory.length} matching records`
                  : `Top ${ranked?.length || 0} catalog results`}
              </p>
            )}
          </>
        ) : (
          <p className="text-xs text-eims-text-muted">
            Issues detected from analysis appear here automatically. Closing a selected incident returns to this list.
          </p>
        )}
      </div>

      <div
        role="tabpanel"
        id="analyzer-records-panel"
        aria-labelledby={
          activeTab === "history"
            ? "analysis-history-tab"
            : activeTab === "catalog"
              ? "event-catalog-tab"
              : "incident-workspace-tab"
        }
        className={`flex-1 min-h-0 overflow-y-auto ${activeTab === "incident" ? "" : "divide-y divide-eims-border"}`}
      >
        {activeTab === "incident" ? (
          incidentId ? (
            <div className="p-4 min-h-[420px]" data-testid="incident-workspace-tab-panel">
              <IncidentWorkspace
                key={incidentId}
                incidentId={incidentId}
                analysisHistoryId={initialAnalysisId ?? undefined}
                onClose={() => {
                  setOpenIncidentsLoaded(false);
                  onCloseIncident?.();
                }}
                onChanged={({ incidentId: nextId }) => {
                  if (nextId) onIncidentChanged?.(nextId);
                }}
              />
            </div>
          ) : (
            <div className="p-4 space-y-4" data-testid="incident-workspace-empty">
              <h3 className="text-base font-semibold text-eims-text">Current issues</h3>
              <p className="text-sm text-eims-text-secondary">
                After you submit evidence, EIMS associates an incident automatically when Incident Core confirms it.
                Select an issue to review findings. Closing detail returns here — not to Analysis History.
              </p>
              {openIncidents.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-eims-text-muted uppercase tracking-wider">Open issues</p>
                  <ul className="space-y-1.5">
                    {openIncidents.map((row) => (
                      <li key={row.incident_id}>
                        <button
                          type="button"
                          className="w-full text-left px-3 py-2 rounded-lg border border-eims-border bg-eims-bg hover:bg-eims-surface-subtle text-sm"
                          onClick={() => onOpenIncident?.(row.incident_id)}
                        >
                          <span className="font-medium text-eims-text">{row.title}</span>
                          <span className="ml-2 text-xs text-eims-text-muted">
                            {row.status === "open" ? "New issue" : row.status} · {row.severity}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : openIncidentsLoaded ? (
                <p className="text-sm text-eims-text-muted">No open incidents are available yet.</p>
              ) : (
                <p className="text-sm text-eims-text-muted">Loading open incidents…</p>
              )}
            </div>
          )
        ) : activeTab === "history" && isLoading ? (
          <div className="p-8 text-center text-eims-text-muted">Loading analysis history...</div>
        ) : activeTab === "catalog" && isLoadingCatalog ? (
          <div className="p-8 text-center text-eims-text-muted">Loading diagnostic reference catalog...</div>
        ) : activeTab === "history" ? (
          visibleHistory.length > 0 ? (
            visibleHistory.map(renderHistoryRow)
          ) : (
            <div className="p-8 text-center text-eims-text-muted">
              {searchTerm.trim() ? "No matching analysis records found." : "No analysis history yet."}
            </div>
          )
        ) : searchTerm.trim() ? (
          ranked && ranked.length > 0 ? (
            ranked.map(({ c }) => renderCatalogRow(c.record))
          ) : (
            <div className="p-8 text-center text-eims-text-muted">No matching catalog entries found.</div>
          )
        ) : sortedCatalog.length > 0 ? (
          sortedCatalog.map(renderCatalogRow)
        ) : (
          <div className="p-8 text-center text-eims-text-muted">
            No diagnostic knowledge available for this source. Parser support does not imply diagnostic coverage.
          </div>
        )}
      </div>
      {activeTab === "history" && hasMoreHistory && !isLoading && (
        <div className="border-t border-eims-border p-3 flex justify-center">
          <button
            type="button"
            disabled={isLoadingMore}
            onClick={() => void handleLoadMoreHistory()}
            className="px-4 py-2 rounded-lg border border-eims-border bg-eims-bg text-sm text-eims-text hover:bg-eims-surface-subtle disabled:opacity-50"
          >
            {isLoadingMore ? "Loading older records..." : "Load older records"}
          </button>
        </div>
      )}

      {/* Detail Modal */}
      {selectedItem && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 sm:p-6 animate-in fade-in duration-200">
          <div
            ref={modalRef}
            className="bg-eims-bg border border-eims-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
          >
            <div className="flex items-center justify-between p-4 border-b border-eims-border bg-eims-surface shrink-0">
              <h2 className="text-lg font-semibold text-eims-text flex items-center gap-2">
                {isSyntheticDemo(selectedItem) ? (
                  <>
                    <ShieldAlert className="w-5 h-5 text-[#A088BC]" />
                    <span>Suspicious Authentication Activity · Synthetic Demo</span>
                  </>
                ) : selectedItem.isCatalog ? (
                  <>
                    <FileText className="w-5 h-5 text-sky-500/80 dark:text-[#7EA8BE]" />
                    <span>Diagnostic Knowledge — {selectedItem.eventId}</span>
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
                  aria-label="Close details"
                  onClick={() => setSelectedItem(null)}
                  className="p-2 hover:bg-eims-surface-subtle rounded-full text-eims-text-muted hover:text-eims-text transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto flex-1 bg-eims-bg space-y-6">
              {!selectedItem.isCatalog && typeof selectedItem.id === "number" && (
                <EventIncidentLink
                  analysisHistoryId={selectedItem.id}
                  observedAt={selectedItem.created_at}
                  eventKey={selectedItem.eventId != null ? String(selectedItem.eventId) : undefined}
                  titleHint={selectedItem.solutionSummary?.title || selectedItem.title}
                  assetId={correlationAssetId}
                  autoEnsure
                  onOpen={(id) => openFromDetail(id, selectedItem.id)}
                  onLinked={(id, association) => {
                    // Refresh open-incident list; do not force-navigate away from Event Detail.
                    // Ambiguous candidates are never auto-opened.
                    setOpenIncidentsLoaded(false);
                    void id;
                    void association;
                  }}
                />
              )}
              <AnalysisResultDetail
                result={selectedItem}
                language={analysisLanguage}
                onDownloadMD={() => downloadMarkdown(selectedItem)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


async function requestHistoryPage(offset: number): Promise<any[]> {
  const response = await fetch(apiUrl(`/api/v1/history/?limit=${HISTORY_PAGE_SIZE}&offset=${offset}`));
  if (!response.ok) throw new Error(`History request failed: HTTP ${response.status}`);
  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

async function requestUnifiedCatalog(facet: CatalogFacet): Promise<{ records: CatalogEntry[]; totals: CatalogTotals }> {
  const params = new URLSearchParams();
  if (facet === "matchable") params.set("analyzer_availability", "matchable");
  if (facet === "class_b") params.set("cert_class", "B");
  if (facet === "eligible") params.set("eligibility", "ELIGIBLE");
  const pageSize = 200;
  let offset = 0;
  let totals: CatalogTotals | null = null;
  let filtered = 0;
  const records: CatalogEntry[] = [];
  while (true) {
    params.set("limit", String(pageSize));
    params.set("offset", String(offset));
    const response = await fetch(apiUrl(`/api/v1/knowledge/catalog?${params.toString()}`));
    if (!response.ok) throw new Error(`Unified catalog request failed: HTTP ${response.status}`);
    const data = await response.json();
    if (!totals && data.totals) {
      totals = {
        governed_records: Number(data.totals.governed_records || 0),
        analyzer_matchable: Number(data.totals.analyzer_matchable || 0),
        other_governed: Number(data.totals.other_governed || 0),
        cert_class_b: Number(data.totals.cert_class_b || 0),
        eligible: Number(data.totals.eligible || 0),
        blocked: Number(data.totals.blocked || 0),
        ineligible: Number(data.totals.ineligible || 0),
        human_approved: Number(data.totals.human_approved || 0),
      };
    }
    filtered = Number(data.filtered_count || 0);
    const batch = Array.isArray(data.records) ? data.records : [];
    records.push(...batch);
    if (records.length >= filtered || batch.length === 0) break;
    offset += pageSize;
  }
  if (!totals) {
    throw new Error("Unified catalog response missing totals");
  }
  return { records, totals };
}
