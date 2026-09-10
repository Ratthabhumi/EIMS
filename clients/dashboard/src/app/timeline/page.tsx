"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, History, ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";
import { TimelineEvent, type TimelineEventData } from "@/components/TimelineEvent";

interface Pagination {
  total_records: number;
  current_page: number;
  page_size: number;
  next_page_cursor: string | null;
}

interface TimelineResponse {
  status: string;
  data: TimelineEventData[];
  pagination: Pagination;
}

const TIMELINE_ENDPOINT = "http://localhost:8000/api/v1/timeline";
const PAGE_SIZE = 50;

const EVENT_TYPES = [
  { value: "", label: "All sources" },
  { value: "audit", label: "Audit" },
  { value: "telemetry", label: "Telemetry" },
  { value: "winlog", label: "WinLog" },
];

const SEVERITIES = [
  { value: "", label: "All severities" },
  { value: "Critical", label: "Critical" },
  { value: "Warning", label: "Warning" },
  { value: "Information", label: "Information" },
];

export default function TimelineDashboard() {
  const [events, setEvents] = useState<TimelineEventData[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [eventType, setEventType] = useState("");
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    const params = new URLSearchParams({ page: String(page), limit: String(PAGE_SIZE) });
    if (eventType) params.set("type", eventType);
    if (severity) params.set("severity", severity);

    fetch(`${TIMELINE_ENDPOINT}?${params.toString()}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Timeline request failed with status ${res.status}`);
        }
        const json = (await res.json()) as TimelineResponse;
        if (cancelled) return;
        setEvents(json.data ?? []);
        setPagination(json.pagination ?? null);
      })
      .catch((err) => {
        if (cancelled || err instanceof DOMException) return;
        setError(true);
        setEvents([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [eventType, severity, page]);

  const applyType = (value: string) => {
    setEventType(value);
    setPage(1);
    setLoading(true);
    setError(false);
  };

  const applySeverity = (value: string) => {
    setSeverity(value);
    setPage(1);
    setLoading(true);
    setError(false);
  };

  const changePage = (nextPage: number) => {
    setPage(nextPage);
    setLoading(true);
    setError(false);
  };

  const totalRecords = pagination?.total_records ?? 0;
  const pageSize = pagination?.page_size ?? PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const hasEvents = events.length > 0;

  const selectClasses =
    "px-3 py-2 text-sm bg-eims-bg border border-eims-border rounded-md text-eims-text focus:outline-none focus:border-eims-accent focus:ring-1 focus:ring-eims-accent transition-colors cursor-pointer";

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 h-full">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-[28px] font-semibold tracking-tight text-eims-text">Unified Timeline</h1>
            <p className="text-eims-text-secondary text-sm mt-1">Chronological events across audit logs, telemetry, and Windows event logs.</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <select
            value={severity}
            onChange={(event) => applySeverity(event.target.value)}
            className={selectClasses}
            aria-label="Filter by severity"
          >
            {SEVERITIES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            value={eventType}
            onChange={(event) => applyType(event.target.value)}
            className={selectClasses}
            aria-label="Filter by source type"
          >
            {EVENT_TYPES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="flex flex-col flex-1 gap-4">
        {loading ? (
          <div className="flex-1 min-h-[320px] flex items-center justify-center text-sm text-eims-text-muted">
            Loading timeline...
          </div>
        ) : error ? (
          <div className="flex-1 min-h-[320px] flex flex-col items-center justify-center gap-2 text-sm">
            <AlertCircle className="w-8 h-8 text-eims-error opacity-70" />
            <span className="text-eims-error">Failed to load timeline. Please try again.</span>
          </div>
        ) : !hasEvents ? (
          <div className="flex-1 min-h-[320px] flex flex-col items-center justify-center gap-3 text-sm text-eims-text-muted">
            <History className="w-8 h-8 opacity-20" />
            <span>No timeline events found.</span>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {events.map((event) => (
              <TimelineEvent key={`${event.type}-${event.id}`} event={event} />
            ))}
          </div>
        )}

        {!loading && !error && totalRecords > 0 ? (
          <div className="flex items-center justify-between pt-1 shrink-0">
            <div className="text-sm text-eims-text-muted">
              {totalRecords.toLocaleString()} events
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-eims-text-muted">
                Page {page} of {totalPages.toLocaleString()}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => changePage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                  className="p-2 bg-eims-surface-subtle hover:bg-eims-surface text-eims-text-secondary hover:text-eims-text rounded-md transition-all active:scale-95 focus:outline-none focus:ring-1 focus:ring-eims-text-secondary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer border border-eims-border"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => changePage(page + 1)}
                  disabled={page >= totalPages}
                  className="p-2 bg-eims-surface-subtle hover:bg-eims-surface text-eims-text-secondary hover:text-eims-text rounded-md transition-all active:scale-95 focus:outline-none focus:ring-1 focus:ring-eims-text-secondary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer border border-eims-border"
                  aria-label="Next page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}