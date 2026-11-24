"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, History, ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";
import { TimelineEvent, type TimelineEventData } from "@/components/TimelineEvent";
import { apiUrl } from "@/lib/api";

/** Bounded background refresh — not a substitute for persistence. */
const REFRESH_MS = 30000;

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

const TIMELINE_ENDPOINT = apiUrl("/api/v1/timeline");
const PAGE_SIZE = 50;

const EVENT_TYPES = [
  { value: "", label: "All sources" },
  { value: "audit", label: "Audit" },
  { value: "incident_transition", label: "Incident transitions" },
  { value: "evidence", label: "Evidence" },
  { value: "verification", label: "Verification" },
  { value: "telemetry", label: "Telemetry" },
  { value: "winlog", label: "WinLog" },
];

const SEVERITIES = [
  { value: "", label: "All severities" },
  { value: "Critical", label: "Critical" },
  { value: "Warning", label: "Warning" },
  { value: "Information", label: "Information" },
];

function TimelineDashboardContent() {
  const searchParams = useSearchParams();
  const initialType = searchParams.get("type") || "";
  const entityId = searchParams.get("entity_id") || "";

  const [events, setEvents] = useState<TimelineEventData[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [eventType, setEventType] = useState(initialType);
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);
  const fingerprintRef = useRef("");
  const inFlightRef = useRef(false);

  const loadTimeline = useCallback(
    async (opts: { silent?: boolean } = {}) => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      if (!opts.silent) {
        setLoading(true);
        setError(false);
      }
      try {
        const params = new URLSearchParams({ page: String(page), limit: String(PAGE_SIZE) });
        if (eventType) params.set("type", eventType);
        if (severity) params.set("severity", severity);
        if (entityId) params.set("entity_id", entityId);

        const res = await fetch(`${TIMELINE_ENDPOINT}?${params.toString()}`, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`Timeline request failed with status ${res.status}`);
        const json = (await res.json()) as TimelineResponse;
        const nextEvents = json.data ?? [];
        const nextPagination = json.pagination ?? null;
        const fingerprint = `${nextPagination?.total_records ?? 0}|${nextEvents[0]?.id ?? ""}|${nextEvents.map((e) => e.id).join(",")}`;
        if (fingerprint !== fingerprintRef.current) {
          fingerprintRef.current = fingerprint;
          setEvents(nextEvents);
          setPagination(nextPagination);
        }
        setError(false);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!opts.silent) {
          setError(true);
          setEvents([]);
          fingerprintRef.current = "";
        }
      } finally {
        clearTimeout(timeout);
        inFlightRef.current = false;
        if (!opts.silent) setLoading(false);
      }
    },
    [eventType, severity, page, entityId],
  );

  useEffect(() => {
    void loadTimeline({ silent: false });
  }, [loadTimeline]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") void loadTimeline({ silent: true });
    };
    const onFocus = () => void loadTimeline({ silent: true });
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onFocus);
    const timer = window.setInterval(() => void loadTimeline({ silent: true }), REFRESH_MS);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onFocus);
      window.clearInterval(timer);
    };
  }, [loadTimeline]);

  const totalRecords = pagination?.total_records ?? 0;
  const pageSize = pagination?.page_size ?? PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const hasEvents = events.length > 0;

  const sourceMix = useMemo(() => {
    const counts = new Map<string, number>();
    for (const e of events) {
      const key = e.type || "unknown";
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([k, n]) => `${k}=${n}`)
      .join(", ");
  }, [events]);

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
            <p className="text-eims-text-secondary text-sm mt-1">
              Read-only engineering timeline: audit journal, incident transitions, evidence, verification, plus legacy telemetry/winlog.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <select
            value={severity}
            onChange={(event) => {
              setSeverity(event.target.value);
              setPage(1);
            }}
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
            onChange={(event) => {
              setEventType(event.target.value);
              setPage(1);
            }}
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

      {!loading && !error && totalRecords > 0 ? (
        <div
          className="rounded-lg border border-eims-border bg-eims-surface-subtle/60 px-4 py-3 text-xs text-eims-text-secondary space-y-1"
          data-testid="timeline-honesty"
        >
          <p>
            Showing {events.length} of {totalRecords} records returned by the API for the current filters. Only sources with real rows appear.
          </p>
          {sourceMix ? <p>Source mix in this page: {sourceMix}</p> : null}
          <p>
            USB Auditor historical audit entries are preserved with original timestamps. Missing actor identity stays “not available in historical source”.
          </p>
        </div>
      ) : null}

      <div className="flex flex-col flex-1 gap-4">
        {loading ? (
          <div className="flex-1 min-h-[320px] flex items-center justify-center text-sm text-eims-text-muted">Loading timeline…</div>
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
            <div className="text-sm text-eims-text-muted">{totalRecords.toLocaleString()} events</div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-eims-text-muted">
                Page {page} of {totalPages.toLocaleString()}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                  className="p-2 bg-eims-surface-subtle hover:bg-eims-surface text-eims-text-secondary hover:text-eims-text rounded-md transition-all active:scale-95 focus:outline-none focus:ring-1 focus:ring-eims-text-secondary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer border border-eims-border"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setPage(page + 1)}
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

export default function TimelineDashboard() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-eims-text-muted">Loading Timeline...</div>}>
      <TimelineDashboardContent />
    </Suspense>
  );
}
