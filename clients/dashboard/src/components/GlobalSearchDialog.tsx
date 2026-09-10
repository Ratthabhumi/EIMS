"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Server, ScrollText, Sparkles, CornerDownLeft, X, AlertCircle } from "lucide-react";

interface SearchResult {
  type: "asset" | "audit" | "analysis";
  id: string;
  title: string;
  subtitle: string;
  url: string;
  timestamp: string | null;
  relevance: number;
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

const TYPE_LABELS: Record<SearchResult["type"], string> = {
  asset: "Asset",
  audit: "Audit",
  analysis: "Analysis",
};

const TYPE_ICONS: Record<SearchResult["type"], typeof Server> = {
  asset: Server,
  audit: ScrollText,
  analysis: Sparkles,
};

const TYPE_BADGE_CLASSES: Record<SearchResult["type"], string> = {
  asset: "text-eims-info bg-eims-info/10 border-eims-info/20",
  audit: "text-eims-secondary bg-eims-secondary/10 border-eims-secondary/20",
  analysis: "text-eims-accent bg-eims-accent/10 border-eims-accent/20",
};

export function GlobalSearchDialog() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

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

  useEffect(() => {
    if (open) {
      inputRef.current?.focus();
    }
  }, [open]);

  const closeDialog = () => {
    setOpen(false);
    setQuery("");
    setResults([]);
    setError(false);
    setHasSearched(false);
    setLoading(false);
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

  useEffect(() => {
    const trimmed = query.trim();
    if (!open || trimmed.length < MIN_QUERY_LENGTH) {
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `${SEARCH_ENDPOINT}?q=${encodeURIComponent(trimmed)}&page=1&limit=20`,
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
        aria-label="Open global search (Ctrl+K)"
      >
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="h-4 w-4 text-eims-text-muted" />
        </div>
        <span className="block w-full truncate">Search the portal...</span>
        <div className="absolute inset-y-0 right-0 pr-2 flex items-center">
          <kbd className="inline-flex items-center border border-eims-border rounded px-2 text-xs font-sans font-medium text-eims-text-muted bg-eims-surface-subtle">
            ⌘K
          </kbd>
        </div>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[15vh] bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={closeDialog}
          role="dialog"
          aria-modal="true"
          aria-label="Global Search"
        >
          <div
            className="w-full max-w-xl bg-eims-surface border border-eims-border rounded-lg shadow-2xl overflow-hidden"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-eims-border">
              <Search className="h-4 w-4 text-eims-text-muted shrink-0" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(event) => handleQueryChange(event.target.value)}
                placeholder="Search assets, audit logs, and analysis..."
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

            <div className="max-h-[50vh] overflow-y-auto">
              {query.trim().length < MIN_QUERY_LENGTH ? (
                <div className="px-5 py-10 text-center text-sm text-eims-text-muted">
                  Type at least {MIN_QUERY_LENGTH} characters to search.
                </div>
              ) : loading ? (
                <div className="px-5 py-10 text-center text-sm text-eims-text-muted">
                  Searching...
                </div>
              ) : error ? (
                <div className="px-5 py-10 text-center text-sm flex flex-col items-center gap-2">
                  <AlertCircle className="w-6 h-6 text-eims-error opacity-70" />
                  <span className="text-eims-error">
                    Search failed. Please try again.
                  </span>
                </div>
              ) : hasSearched && results.length === 0 ? (
                <div className="px-5 py-10 text-center text-sm text-eims-text-muted">
                  No results found for &ldquo;{query.trim()}&rdquo;.
                </div>
              ) : (
                <ul className="divide-y divide-eims-border">
                  {results.map((result) => {
                    const TypeIcon = TYPE_ICONS[result.type] ?? Search;
                    return (
                      <li key={`${result.type}-${result.id}`}>
                        <button
                          type="button"
                          onClick={() => handleSelect(result)}
                          className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-eims-surface-subtle/60 transition-colors group cursor-pointer"
                        >
                          <div className="w-8 h-8 rounded-md bg-eims-surface-subtle border border-eims-border flex items-center justify-center shrink-0 mt-0.5">
                            <TypeIcon className="w-4 h-4 text-eims-text-secondary group-hover:text-eims-accent transition-colors" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-eims-text truncate">
                                {result.title}
                              </span>
                              <span
                                className={`shrink-0 inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide rounded border ${TYPE_BADGE_CLASSES[result.type] ?? ""}`}
                              >
                                {TYPE_LABELS[result.type] ?? result.type}
                              </span>
                            </div>
                            {result.subtitle ? (
                              <div className="text-xs text-eims-text-secondary truncate mt-0.5">
                                {result.subtitle}
                              </div>
                            ) : null}
                          </div>
                          <CornerDownLeft className="w-3.5 h-3.5 text-eims-text-muted opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-1.5" />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}