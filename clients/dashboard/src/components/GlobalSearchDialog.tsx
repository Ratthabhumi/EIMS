"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Server,
  ScrollText,
  Sparkles,
  CornerDownLeft,
  X,
  AlertCircle,
  Compass,
  ShieldAlert,
  Usb,
  ScanText,
  Activity,
  Star,
  ChevronRight,
} from "lucide-react";

export type SearchDomainType =
  | "navigation"
  | "asset"
  | "audit"
  | "analysis"
  | "winlog"
  | "usb"
  | "ocr"
  | "telemetry"
  | "evaluation";

export interface SearchResult {
  type: SearchDomainType | string;
  id: string;
  title: string;
  subtitle: string;
  url: string;
  timestamp: string | null;
  relevance: number;
  result_kind?: "navigation" | "entity" | string;
  metadata: Record<string, unknown>;
}

interface SearchResponse {
  status: string;
  data: SearchResult[];
  pagination: {
    total_records: number;
    current_page: number;
    page_size: number;
    next_page_cursor: string | null;
  };
}

const SEARCH_ENDPOINT = "http://localhost:8000/api/v1/search";
const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 300;

const TYPE_LABELS: Record<string, string> = {
  navigation: "Command / Page",
  asset: "Asset",
  audit: "Audit Journal",
  analysis: "AI Analysis",
  winlog: "WinLog Event",
  usb: "USB Evidence",
  ocr: "Sticker OCR",
  telemetry: "Vitals Stream",
  evaluation: "Evaluation",
};

const TYPE_ICONS: Record<string, typeof Server> = {
  navigation: Compass,
  asset: Server,
  audit: ScrollText,
  analysis: Sparkles,
  winlog: ShieldAlert,
  usb: Usb,
  ocr: ScanText,
  telemetry: Activity,
  evaluation: Star,
};

const TYPE_BADGE_CLASSES: Record<string, string> = {
  navigation: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
  asset: "text-eims-info bg-eims-info/10 border-eims-info/20",
  audit: "text-eims-secondary bg-eims-secondary/10 border-eims-secondary/20",
  analysis: "text-eims-accent bg-eims-accent/10 border-eims-accent/20",
  winlog: "text-red-400 bg-red-500/10 border-red-500/20",
  usb: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  ocr: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  telemetry: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  evaluation: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
};

interface ResultGroup {
  id: string;
  name: string;
  order: number;
  items: SearchResult[];
}

const GROUP_CONFIG: Record<string, { name: string; order: number }> = {
  navigation: { name: "Navigation & Commands", order: 1 },
  asset: { name: "Infrastructure Assets", order: 2 },
  audit: { name: "Security & Audit Journal", order: 3 },
  winlog: { name: "Windows Event Logs", order: 4 },
  usb: { name: "Endpoint Evidence (USB Auditor)", order: 5 },
  analysis: { name: "AI Log Analysis", order: 6 },
  ocr: { name: "Sticker OCR & Hardware Recognition", order: 7 },
  telemetry: { name: "Telemetry & Host Vitals", order: 8 },
  evaluation: { name: "Service Evaluations", order: 9 },
};

export function GlobalSearchDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Group results logically
  const groupedResults = useMemo(() => {
    const groups: Record<string, SearchResult[]> = {};
    for (const r of results) {
      const gKey = r.result_kind === "navigation" ? "navigation" : r.type;
      if (!groups[gKey]) {
        groups[gKey] = [];
      }
      groups[gKey].push(r);
    }

    const groupList: ResultGroup[] = [];
    for (const [key, items] of Object.entries(groups)) {
      const conf = GROUP_CONFIG[key] || { name: key.toUpperCase(), order: 99 };
      groupList.push({
        id: key,
        name: conf.name,
        order: conf.order,
        items,
      });
    }
    groupList.sort((a, b) => a.order - b.order);
    return groupList;
  }, [results]);

  // Flattened order for keyboard navigation indexing
  const flattenedResults = useMemo(() => {
    return groupedResults.flatMap((g) => g.items);
  }, [groupedResults]);

  // Reset selected index when query or results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [results]);

  // Open/close keyboard shortcuts (Cmd+K / Ctrl+K / Escape)
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((prev) => !prev);
        return;
      }
      if (open && event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // Focus input when dialog opens
  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  // Arrow key & Enter navigation
  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (flattenedResults.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % flattenedResults.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + flattenedResults.length) % flattenedResults.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const current = flattenedResults[selectedIndex];
      if (current) {
        handleSelect(current);
      }
    }
  };

  const closeDialog = () => {
    setOpen(false);
    setQuery("");
    setResults([]);
    setError(false);
    setHasSearched(false);
    setLoading(false);
    setSelectedIndex(0);
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (value.trim().length < MIN_QUERY_LENGTH) {
      setLoading(false);
      setError(false);
      setResults([]);
      setHasSearched(false);
    } else {
      setLoading(true);
      setError(false);
    }
  };

  // Debounced search query fetching
  useEffect(() => {
    const trimmed = query.trim();
    if (!open || trimmed.length < MIN_QUERY_LENGTH) {
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${SEARCH_ENDPOINT}?q=${encodeURIComponent(trimmed)}&page=1&limit=30`,
          { signal: controller.signal }
        );
        if (!res.ok) {
          throw new Error(`Search request failed with status ${res.status}`);
        }
        const json = (await res.json()) as SearchResponse;
        setResults(json.data ?? []);
        setHasSearched(true);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setError(true);
        setResults([]);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, open]);

  const handleSelect = (result: SearchResult) => {
    setOpen(false);
    router.push(result.url);
  };

  return (
    <div className="flex items-center w-full max-w-md">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="relative w-full pl-10 pr-12 py-2 border border-eims-border rounded-md leading-5 bg-eims-bg placeholder-eims-text-muted focus:outline-none focus:border-eims-accent focus:ring-1 focus:ring-eims-accent sm:text-sm transition-colors text-left text-eims-text-muted cursor-pointer"
        aria-label="Open universal command search (Ctrl+K)"
      >
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="h-4 w-4 text-eims-text-muted" />
        </div>
        <span className="block w-full truncate">Search portal, assets, logs, commands...</span>
        <div className="absolute inset-y-0 right-0 pr-2 flex items-center">
          <kbd className="inline-flex items-center border border-eims-border rounded px-2 text-xs font-sans font-medium text-eims-text-muted bg-eims-surface-subtle">
            ⌘K
          </kbd>
        </div>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[10vh] sm:pt-[12vh] bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={closeDialog}
          role="dialog"
          aria-modal="true"
          aria-label="Universal Command Center"
        >
          <div
            className="w-full max-w-2xl bg-eims-surface border border-eims-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]"
            onClick={(event) => event.stopPropagation()}
          >
            {/* Search Input Bar */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-eims-border bg-eims-surface shrink-0">
              <Search className="h-5 w-5 text-eims-text-muted shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(event) => handleQueryChange(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a command, route, asset (KEL-PROD), WinLog (4625), USB, OCR..."
                className="w-full bg-transparent text-sm text-eims-text placeholder-eims-text-muted focus:outline-none"
                aria-label="Global search query"
              />
              <kbd className="hidden sm:inline-flex items-center border border-eims-border rounded px-1.5 text-xs font-sans font-medium text-eims-text-muted bg-eims-surface-subtle">
                ESC
              </kbd>
              <button
                type="button"
                onClick={closeDialog}
                className="p-1 rounded text-eims-text-muted hover:text-eims-text hover:bg-eims-surface-subtle transition-colors cursor-pointer"
                aria-label="Close global search"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Results Scroll Container */}
            <div ref={listRef} className="flex-1 overflow-y-auto min-h-[160px]">
              {query.trim().length < MIN_QUERY_LENGTH ? (
                <div className="px-5 py-12 text-center text-sm text-eims-text-muted space-y-2">
                  <div className="text-xs uppercase tracking-wider font-semibold text-eims-text-secondary">
                    EIMS Universal Command Center
                  </div>
                  <div>Type at least {MIN_QUERY_LENGTH} characters to search pages, entities, and evidence.</div>
                  <div className="pt-2 flex flex-wrap justify-center gap-1.5 text-xs">
                    {["timeline", "usb", "ocr", "analyzer", "4625", "gpu", "endpoint", "evaluation"].map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        onClick={() => handleQueryChange(chip)}
                        className="px-2 py-0.5 rounded border border-eims-border bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text hover:border-eims-accent transition-colors cursor-pointer"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
              ) : loading ? (
                <div className="px-5 py-12 text-center text-sm text-eims-text-muted flex items-center justify-center gap-2">
                  <div className="w-4 h-4 rounded-full border-2 border-eims-accent border-t-transparent animate-spin" />
                  <span>Searching operational index...</span>
                </div>
              ) : error ? (
                <div className="px-5 py-12 text-center text-sm flex flex-col items-center gap-2">
                  <AlertCircle className="w-6 h-6 text-eims-error opacity-70" />
                  <span className="text-eims-error">Search request failed. Please try again.</span>
                </div>
              ) : hasSearched && results.length === 0 ? (
                <div className="px-5 py-12 text-center text-sm text-eims-text-muted space-y-1">
                  <div>No results found for &ldquo;{query.trim()}&rdquo;.</div>
                  <div className="text-xs text-eims-text-secondary">
                    Try searching by hostname, IP address, event ID (e.g. 4625), or page name (e.g. timeline).
                  </div>
                </div>
              ) : (
                <div className="py-2 divide-y divide-eims-border/40">
                  {groupedResults.map((group) => (
                    <div key={group.id} className="py-1.5">
                      {/* Section Heading */}
                      <div className="px-4 py-1.5 text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider flex items-center justify-between">
                        <span>{group.name}</span>
                        <span className="text-[10px] text-eims-text-muted lowercase">
                          {group.items.length} {group.items.length === 1 ? "hit" : "hits"}
                        </span>
                      </div>

                      <ul className="space-y-0.5 px-2">
                        {group.items.map((result) => {
                          const itemIndex = flattenedResults.indexOf(result);
                          const isSelected = itemIndex === selectedIndex;
                          const TypeIcon = TYPE_ICONS[result.type] ?? Search;
                          const badgeStyle = TYPE_BADGE_CLASSES[result.type] ?? "text-eims-text-secondary border-eims-border";
                          const label = TYPE_LABELS[result.type] ?? result.type;

                          return (
                            <li key={`${result.type}-${result.id}`}>
                              <button
                                type="button"
                                onClick={() => handleSelect(result)}
                                onMouseEnter={() => setSelectedIndex(itemIndex)}
                                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all group cursor-pointer ${
                                  isSelected
                                    ? "bg-eims-accent/15 border border-eims-accent/30 shadow-sm"
                                    : "hover:bg-eims-surface-subtle/70 border border-transparent"
                                }`}
                              >
                                {/* Domain Icon */}
                                <div
                                  className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 border transition-colors ${
                                    isSelected
                                      ? "bg-eims-accent text-white border-eims-accent"
                                      : "bg-eims-surface-subtle border-eims-border text-eims-text-secondary group-hover:text-eims-accent"
                                  }`}
                                >
                                  <TypeIcon className="w-4 h-4" />
                                </div>

                                {/* Text & Badges */}
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`text-sm font-medium truncate ${
                                        isSelected ? "text-eims-accent font-semibold" : "text-eims-text"
                                      }`}
                                    >
                                      {result.title}
                                    </span>
                                    <span
                                      className={`shrink-0 inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide rounded border ${badgeStyle}`}
                                    >
                                      {label}
                                    </span>
                                  </div>
                                  {result.subtitle ? (
                                    <div className="text-xs text-eims-text-secondary truncate mt-0.5">
                                      {result.subtitle}
                                    </div>
                                  ) : null}
                                </div>

                                {/* Context Navigation Action */}
                                <div className="shrink-0 flex items-center gap-1 text-xs text-eims-text-muted">
                                  {isSelected ? (
                                    <span className="inline-flex items-center gap-1 text-eims-accent text-[11px] font-medium">
                                      <span>Open</span>
                                      <CornerDownLeft className="w-3.5 h-3.5" />
                                    </span>
                                  ) : (
                                    <ChevronRight className="w-4 h-4 opacity-0 group-hover:opacity-60 transition-opacity" />
                                  )}
                                </div>
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Dialog Footer with Navigation Tips */}
            <div className="px-4 py-2.5 border-t border-eims-border bg-eims-surface-subtle/50 flex items-center justify-between text-[11px] text-eims-text-muted shrink-0">
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1">
                  <kbd className="px-1 py-0.5 rounded border border-eims-border bg-eims-surface text-[10px]">↑</kbd>
                  <kbd className="px-1 py-0.5 rounded border border-eims-border bg-eims-surface text-[10px]">↓</kbd>
                  <span>Navigate</span>
                </span>
                <span className="inline-flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 rounded border border-eims-border bg-eims-surface text-[10px]">↵</kbd>
                  <span>Open</span>
                </span>
                <span className="inline-flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 rounded border border-eims-border bg-eims-surface text-[10px]">ESC</kbd>
                  <span>Close</span>
                </span>
              </div>
              <div>
                {flattenedResults.length > 0 ? (
                  <span>{flattenedResults.length} {flattenedResults.length === 1 ? "result" : "results"}</span>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}