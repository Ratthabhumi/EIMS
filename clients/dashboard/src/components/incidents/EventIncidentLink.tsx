"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "@/lib/api";
import { Badge, btn, field, json, statusTone, rootTone, type Incident } from "./shared";
import {
  associationBannerClass,
  ensureIncidentForAnalysis,
  incidentStatusLabel,
  rootCauseLabel,
  type IncidentAssociation,
} from "@/lib/incident-orchestration";

export type EventIncidentLinkProps = {
  /** analysis_history.id of the event shown in Event Detail. */
  analysisHistoryId: number;
  /** When the analysis happened (ISO string). Defaults to now. */
  observedAt?: string;
  /** Optional event key (e.g. the Windows Event ID). Passed to Incident Core for correlation. */
  eventKey?: string;
  /** Optional title hint when creating a new incident. */
  titleHint?: string;
  /** Optional known asset_id for correlation (never invent from hostname alone). */
  assetId?: string | null;
  /**
   * When true (default), after mount call Incident Core ensure (lookup → create_from_evidence).
   * Uses backend idempotency; does not invent associations in the browser.
   */
  autoEnsure?: boolean;
  /** Called with the incident id to show in the Incident Workspace. */
  onOpen: (incidentId: string) => void;
  /** Called after an event was linked or an incident created/associated. */
  onLinked?: (incidentId: string, association?: IncidentAssociation) => void;
};

/**
 * Automatic-first incident association for an analyzed event.
 * Primary path: backend ensure (idempotent). Manual link remains for correcting association.
 * Privileged lifecycle actions are never implied here.
 */
export default function EventIncidentLink({
  analysisHistoryId,
  observedAt,
  eventKey,
  titleHint,
  assetId,
  autoEnsure = true,
  onOpen,
  onLinked,
}: EventIncidentLinkProps) {
  const [association, setAssociation] = useState<IncidentAssociation | null>(null);
  const [busy, setBusy] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [openIncidents, setOpenIncidents] = useState<Incident[]>([]);
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  /** Prevent React Strict Mode / remount double POST for the same analysis id. */
  const ensuredFor = useRef<number | null>(null);
  const inFlight = useRef(false);

  const runEnsure = useCallback(async (force = false) => {
    if (inFlight.current) return;
    if (!force && ensuredFor.current === analysisHistoryId) return;
    inFlight.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await ensureIncidentForAnalysis({
        analysisHistoryId,
        observedAt,
        eventKey,
        titleHint,
        assetId,
      });
      ensuredFor.current = analysisHistoryId;
      setAssociation(result);
      if (result.outcome === "failed") {
        setError(result.message);
      } else {
        setMessage(result.message);
      }
      if (
        result.incidentId
        && (result.outcome === "created"
          || result.outcome === "correlated"
          || result.outcome === "already_linked"
          || result.outcome === "ambiguous")
      ) {
        onLinked?.(result.incidentId, result);
      }
      try {
        const list = await fetch(apiUrl("/api/v1/incidents?limit=100"), { cache: "no-store" }).then(json);
        setOpenIncidents((list.data as Incident[]).filter((i) => !["resolved", "closed"].includes(i.status)));
      } catch {
        /* advanced list is optional */
      }
    } catch (cause) {
      setAssociation({
        outcome: "failed",
        incidentId: null,
        message: cause instanceof Error ? cause.message : "Incident processing failed.",
      });
      setError(cause instanceof Error ? cause.message : "Incident processing failed.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, [analysisHistoryId, observedAt, eventKey, titleHint, assetId, onLinked]);

  useEffect(() => {
    if (!autoEnsure) return;
    // runEnsure is stable enough via inFlight/ensuredFor guards; include it for lint.
    const tmr = window.setTimeout(() => { void runEnsure(false); }, 0);
    return () => window.clearTimeout(tmr);
  }, [autoEnsure, analysisHistoryId, runEnsure]);

  const evidence = {
    source_type: "analysis",
    source_id: String(analysisHistoryId),
    observed_at: observedAt ?? new Date().toISOString(),
  };

  const link = async () => {
    if (busy || !target) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const incident = await fetch(apiUrl(`/api/v1/incidents/${target}/evidence`), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ evidence: [evidence] }),
      }).then(json);
      const okMsg = incident.summary?.evidence_added
        ? "Evidence linked to the selected incident."
        : "That evidence was already linked to this incident.";
      setMessage(okMsg);
      const next: IncidentAssociation = {
        outcome: "already_linked",
        incidentId: incident.incident_id,
        title: incident.title,
        status: incident.status,
        severity: incident.severity,
        rootCauseState: incident.root_cause_state,
        message: okMsg,
      };
      setAssociation(next);
      onLinked?.(incident.incident_id, next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not link the event");
    } finally {
      setBusy(false);
    }
  };

  const primaryBtn =
    "inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-eims-accent hover:bg-eims-accent-hover text-white text-sm font-semibold disabled:opacity-50";

  const outcome = association?.outcome;
  const bannerTone = outcome ? associationBannerClass(outcome) : "border-eims-border text-eims-text-secondary";

  return (
    <section
      aria-label="Incident association"
      className="rounded-xl border-2 border-eims-accent/40 bg-eims-surface p-4 space-y-3 text-sm shadow-sm"
      data-testid="event-incident-link"
      id="event-incident-actions"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-eims-text">Incident association</h3>
        <p className="text-[11px] text-eims-text-muted">
          Automatic via Incident Core · idempotent per analysis record
        </p>
      </div>

      {busy && !association ? (
        <p className="text-xs text-eims-text-muted" data-testid="incident-assoc-loading">
          Associating evidence with an incident…
        </p>
      ) : null}

      {error ? <div role="alert" className="text-xs text-red-600">{error}</div> : null}

      {association && association.outcome !== "failed" ? (
        <div
          role="status"
          className={`rounded-lg border px-3 py-2 text-xs space-y-2 ${bannerTone}`}
          data-testid="incident-assoc-status"
          data-outcome={association.outcome}
        >
          <p className="font-medium">{association.message}</p>
          {association.outcome === "ambiguous" && association.created ? (
            <p className="text-[11px] text-amber-800 dark:text-amber-300">
              A new incident row may exist, but correlation was not confirmed. Do not treat candidates as merged.
            </p>
          ) : null}
          {association.candidates && association.candidates.length > 0 ? (
            <ul className="list-disc pl-4 space-y-0.5" data-testid="ambiguous-candidates">
              {association.candidates.map((c) => (
                <li key={c.incidentId}>
                  <button
                    type="button"
                    className="text-eims-accent hover:underline"
                    onClick={() => onOpen(c.incidentId)}
                  >
                    Review candidate {c.incidentId.slice(0, 8)}…
                  </button>
                  {c.confidence ? ` · ${c.confidence}` : ""}
                  {c.reasons?.length ? ` · ${c.reasons.join(", ")}` : ""}
                </li>
              ))}
            </ul>
          ) : null}
          {association.incidentId ? (
            <>
              <div className="flex flex-wrap items-center gap-1">
                {association.status ? (
                  <Badge tone={statusTone(association.status)}>{incidentStatusLabel(association.status)}</Badge>
                ) : null}
                {association.severity ? <Badge>{association.severity}</Badge> : null}
                {association.rootCauseState ? (
                  <Badge tone={rootTone(association.rootCauseState)}>
                    {rootCauseLabel(association.rootCauseState)}
                  </Badge>
                ) : null}
                {association.outcome === "ambiguous" ? (
                  <Badge tone="warn">Ambiguous — not correlated</Badge>
                ) : null}
              </div>
              {association.title ? (
                <div className="font-medium text-eims-text break-words">{association.title}</div>
              ) : null}
              <button
                type="button"
                className={primaryBtn}
                onClick={() => onOpen(association.incidentId!)}
                data-testid="open-associated-incident"
              >
                {association.outcome === "ambiguous"
                  ? "Open created incident (manual review)"
                  : "Review in Incident Workspace"}
              </button>
            </>
          ) : (
            <p>No incident association available. You can link manually below.</p>
          )}
        </div>
      ) : null}

      {message && association?.outcome === "failed" ? (
        <div role="status" className="text-xs text-eims-text-muted">{message}</div>
      ) : null}

      <div className="border-t border-eims-border pt-2">
        <button
          type="button"
          className="text-xs text-eims-accent hover:underline"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
        >
          {showAdvanced ? "Hide advanced linking" : "Advanced: link to a different open incident"}
        </button>
        {showAdvanced ? (
          <div className="mt-2 space-y-2">
            <p className="text-[11px] text-eims-text-muted">
              Use only to correct a mistaken association. Correlation and merge decisions stay in Incident Core.
            </p>
            <label className="block text-xs text-eims-text-secondary" htmlFor="ev-inc-target">
              Open incident
            </label>
            <select
              id="ev-inc-target"
              className={field}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              disabled={openIncidents.length === 0}
            >
              <option value="">
                {openIncidents.length === 0 ? "No open incidents loaded" : "Choose incident…"}
              </option>
              {openIncidents.map((i) => (
                <option key={i.incident_id} value={i.incident_id}>
                  {i.title} ({incidentStatusLabel(i.status)})
                </option>
              ))}
            </select>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={btn} disabled={busy || !target} onClick={link}>
                Link evidence
              </button>
              <button type="button" className={btn} disabled={busy} onClick={() => void runEnsure(true)}>
                Retry automatic association
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
