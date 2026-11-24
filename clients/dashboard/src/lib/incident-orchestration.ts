/**
 * Frontend orchestration over existing Incident Core HTTP contracts.
 * Never invents endpoints. Never claims success without a confirmed response.
 * Idempotency and correlation belong to the backend (create_from_evidence).
 */
import { apiUrl } from "@/lib/api";

export type IncidentAssociationOutcome =
  | "created"
  | "correlated"
  | "already_linked"
  | "ambiguous"
  | "unavailable"
  | "failed";

export type CorrelationCandidate = {
  incidentId: string;
  confidence?: string;
  reasons?: string[];
};

export type IncidentAssociation = {
  outcome: IncidentAssociationOutcome;
  incidentId: string | null;
  title?: string;
  status?: string;
  severity?: string;
  rootCauseState?: string;
  message: string;
  /** Backend match field when present. */
  match?: string;
  created?: boolean;
  /** From summary.correlation.candidates when match is ambiguous_not_merged. */
  candidates?: CorrelationCandidate[];
};

type LinkedRow = {
  incident_id: string;
  title: string;
  status: string;
  severity: string;
  root_cause_state: string;
};

export type EnsureIncidentInput = {
  analysisHistoryId: number;
  observedAt?: string;
  /** When set, passed as source_event_key so Incident Core may correlate. */
  eventKey?: string | null;
  titleHint?: string;
  severity?: string;
  /** When known (never invent from hostname alone), passed for Incident Core correlation. */
  assetId?: string | null;
  /** Injected fetch for tests. */
  fetchImpl?: typeof fetch;
};

async function readJson(res: Response): Promise<Record<string, unknown>> {
  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return body;
}

function usableEventKey(eventKey?: string | null): string | undefined {
  if (!eventKey) return undefined;
  const trimmed = String(eventKey).trim();
  if (!trimmed) return undefined;
  const lower = trimmed.toLowerCase();
  if (lower === "unknown" || lower === "n/a" || lower === "none") return undefined;
  return trimmed.slice(0, 160);
}

function fieldsFrom(body: Record<string, unknown>) {
  return {
    title: typeof body.title === "string" ? body.title : undefined,
    status: typeof body.status === "string" ? body.status : undefined,
    severity: typeof body.severity === "string" ? body.severity : undefined,
    rootCauseState: typeof body.root_cause_state === "string" ? body.root_cause_state : undefined,
  };
}

/**
 * Map Incident Core POST /incidents response.
 * Backend contract (schemas.py): created | event_already_linked | correlated_with_open_incident | ambiguous_not_merged.
 * Important: ambiguous_not_merged can arrive with created=true — must NOT be treated as a clear "created" success for auto-navigation.
 */
export function outcomeFromCreate(body: Record<string, unknown>): IncidentAssociation {
  const incidentId = typeof body.incident_id === "string" ? body.incident_id : null;
  const created = body.created === true;
  const match = typeof body.match === "string" ? body.match : undefined;
  const extra = fieldsFrom(body);
  if (!incidentId) {
    return {
      outcome: "failed",
      incidentId: null,
      message: "Incident Core returned no incident id.",
      match,
      created,
    };
  }
  // Check ambiguous before created — Claude emits match=ambiguous_not_merged with created=true.
  if (
    match === "ambiguous_not_merged"
    || match === "uncorrelated"
    || match === "ambiguous"
    || match === "correlation_unresolved"
  ) {
    const summary = body.summary as Record<string, unknown> | undefined;
    const correlation = summary?.correlation as Record<string, unknown> | undefined;
    const rawCandidates = Array.isArray(correlation?.candidates) ? correlation.candidates : [];
    const candidates: CorrelationCandidate[] = [];
    for (const c of rawCandidates) {
      const row = c as Record<string, unknown>;
      const id = typeof row.incident_id === "string" ? row.incident_id : null;
      if (!id) continue;
      candidates.push({
        incidentId: id,
        confidence: typeof row.confidence === "string" ? row.confidence : undefined,
        reasons: Array.isArray(row.reasons) ? row.reasons.map(String) : undefined,
      });
    }
    return {
      outcome: "ambiguous",
      incidentId,
      ...extra,
      message: created
        ? "Created separately — possible related incidents need your review. Not a confirmed correlation."
        : "Correlation was ambiguous — review before treating as linked.",
      match,
      created,
      candidates: candidates.length ? candidates : undefined,
    };
  }
  if (match === "event_already_linked") {
    return {
      outcome: "already_linked",
      incidentId,
      ...extra,
      message: "Evidence already linked; existing incident opened.",
      match,
      created: false,
    };
  }
  if (match === "correlated_with_open_incident") {
    return {
      outcome: "correlated",
      incidentId,
      ...extra,
      message: "Added to an existing incident (Incident Core correlation).",
      match,
      created: false,
    };
  }
  if (match === "created" || (created && !match)) {
    return {
      outcome: "created",
      incidentId,
      ...extra,
      message: "Incident created.",
      match: match || "created",
      created: true,
    };
  }
  // Unknown match with an id: never treat as success.
  return {
    outcome: "ambiguous",
    incidentId,
    ...extra,
    message: "Incident id returned without a recognized match status — treat as unresolved until confirmed.",
    match,
    created,
  };
}

/** Outcomes that justify automatic Workspace navigation. */
export function isClearAssociationSuccess(outcome: IncidentAssociationOutcome): boolean {
  return outcome === "created" || outcome === "correlated" || outcome === "already_linked";
}

/** Lookup only — does not create. */
export async function lookupIncidentByAnalysis(
  analysisHistoryId: number,
  fetchImpl: typeof fetch = fetch,
): Promise<IncidentAssociation> {
  try {
    const res = await fetchImpl(
      apiUrl(`/api/v1/incidents/by-evidence?source_type=analysis&source_id=${analysisHistoryId}`),
      { cache: "no-store" },
    );
    const rows = (await readJson(res)) as unknown as LinkedRow[];
    const first = Array.isArray(rows) ? rows[0] : undefined;
    if (!first) {
      return {
        outcome: "unavailable",
        incidentId: null,
        message: "No incident association available yet.",
      };
    }
    return {
      outcome: "already_linked",
      incidentId: first.incident_id,
      title: first.title,
      status: first.status,
      severity: first.severity,
      rootCauseState: first.root_cause_state,
      message: "Evidence already linked; existing incident opened.",
      match: "event_already_linked",
      created: false,
    };
  } catch (cause) {
    return {
      outcome: "failed",
      incidentId: null,
      message: cause instanceof Error ? cause.message : "Incident lookup failed.",
    };
  }
}

/**
 * Ensure analysis evidence is associated with an incident via Incident Core.
 * 1) Lookup by-evidence (idempotent read).
 * 2) If unbound, POST /api/v1/incidents (backend create_from_evidence).
 * Never deduplicates in the browser as a substitute for backend guarantees.
 */
export async function ensureIncidentForAnalysis(input: EnsureIncidentInput): Promise<IncidentAssociation> {
  const fetchImpl = input.fetchImpl ?? fetch;
  const existing = await lookupIncidentByAnalysis(input.analysisHistoryId, fetchImpl);
  if (existing.outcome === "already_linked" && existing.incidentId) return existing;
  if (existing.outcome === "failed") return existing;

  const eventKey = usableEventKey(input.eventKey);
  const evidence: Record<string, unknown> = {
    source_type: "analysis",
    source_id: String(input.analysisHistoryId),
    observed_at: input.observedAt ?? new Date().toISOString(),
  };
  if (eventKey) evidence.source_event_key = eventKey;

  try {
    const assetId = typeof input.assetId === "string" ? input.assetId.trim() : "";
    const res = await fetchImpl(apiUrl("/api/v1/incidents"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: input.titleHint?.trim() || undefined,
        severity: input.severity || "medium",
        ...(assetId ? { asset_id: assetId } : {}),
        evidence: [evidence],
      }),
    });
    const body = await readJson(res);
    return outcomeFromCreate(body);
  } catch (cause) {
    return {
      outcome: "failed",
      incidentId: null,
      message: cause instanceof Error ? cause.message : "Incident processing failed.",
    };
  }
}

/** User-facing status / diagnosis labels (presentation only). */
export function incidentStatusLabel(status: string): string {
  const map: Record<string, string> = {
    open: "New issue",
    triage: "Investigating",
    investigating: "Investigating",
    resolved: "Resolved",
    closed: "Closed",
  };
  return map[status] || status;
}

export function rootCauseLabel(state: string): string {
  const map: Record<string, string> = {
    unknown: "Cause unknown",
    hypothesized: "Possible cause",
    hypothesis: "Possible cause",
    confirmed: "Cause confirmed",
  };
  return map[state] || state;
}

export function associationBannerClass(outcome: IncidentAssociationOutcome): string {
  if (outcome === "failed") return "border-red-500/40 text-red-700 dark:text-red-300";
  if (outcome === "unavailable" || outcome === "ambiguous") {
    return "border-amber-500/40 text-amber-800 dark:text-amber-200";
  }
  return "border-emerald-500/40 text-emerald-800 dark:text-emerald-300";
}
