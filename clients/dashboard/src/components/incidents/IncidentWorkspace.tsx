"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { AlertCircle, X } from "lucide-react";
import { apiUrl } from "@/lib/api";
import {
  Assurance, Badge, DIAGNOSIS_LABEL, Disclosure, EMPTY_PAGE, KnowledgeLine, OUTCOMES, Sub,
  btn, field, json, lines, loadPage, rootTone, severityTone, statusTone, when,
  type Current, type Detail, type Diagnosis, type Page, type ProposalLink, type Remediation, type Snapshot, type WorkflowEvent,
} from "./shared";
import { incidentStatusLabel, rootCauseLabel } from "@/lib/incident-orchestration";
import EngineerNotes from "./EngineerNotes";

export type IncidentWorkspaceProps = {
  /** The incident to show. Render with key={incidentId} so all local state resets on change. */
  incidentId: string;
  /** The analysis record selected in the Analyzer (analysis_history.id), if any. Used only as context. */
  analysisHistoryId?: number | null;
  /** Called after any successful mutation so the host can refresh badges/lists. */
  onChanged?: (event: { incidentId: string }) => void;
  /** When provided, a collapse/close control is shown. The host owns visibility and layout. */
  onClose?: () => void;
};

export default function IncidentWorkspace({ incidentId, analysisHistoryId, onChanged, onClose }: IncidentWorkspaceProps) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [diagnoses, setDiagnoses] = useState<Page<Diagnosis>>(EMPTY_PAGE);
  const [remediations, setRemediations] = useState<Page<Remediation>>(EMPTY_PAGE);
  const [events, setEvents] = useState<Page<WorkflowEvent>>(EMPTY_PAGE);
  const [proposals, setProposals] = useState<ProposalLink[]>([]);
  const [proposalStatus, setProposalStatus] = useState<Record<number, string>>({});
  const [current, setCurrent] = useState<Record<string, Current | null>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const [hypothesis, setHypothesis] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [confidence, setConfidence] = useState("low");
  const [supporting, setSupporting] = useState<string[]>([]);
  const [catalogId, setCatalogId] = useState("");
  const [refAnalysis, setRefAnalysis] = useState(true);
  const [rem, setRem] = useState({ action: "", risk: "", rollback_plan: "", expected_verification_criteria: "", impact: "", catalog_id: "" });
  const [exec, setExec] = useState<Record<string, { actual_action: string; outcome: string; outcome_notes: string }>>({});
  const [closing, setClosing] = useState<Record<string, { mode: "reject" | "supersede"; reason: string; by: string }>>({});
  const [kp, setKp] = useState({ title: "", root_cause: "", steps: "", evidence: "", validation: "", rollback: "", resolution: "resolved", risk: "medium", diagnosis: "", remediation: "" });

  const latest = useRef(0);
  const loadDetail = useCallback(async (id: string) => {
    if (!id) return;
    const token = ++latest.current;
    setError("");
    const base = `/api/v1/incidents/${id}`;
    // Incident identity must load even when workflow sub-routes fail (Claude-owned 500s).
    let d: Detail;
    try {
      d = await fetch(apiUrl(base), { cache: "no-store" }).then(json);
    } catch (cause) {
      if (token === latest.current) {
        setDetail(null);
        setError(cause instanceof Error ? cause.message : "Incident could not be loaded");
      }
      return;
    }
    if (token !== latest.current) return;
    setDetail(d);

    const secondaryErrors: string[] = [];
    const settle = async <T,>(label: string, run: () => Promise<T>, fallback: T): Promise<T> => {
      try { return await run(); }
      catch (cause) {
        secondaryErrors.push(`${label}: ${cause instanceof Error ? cause.message : "failed"}`);
        return fallback;
      }
    };
    const empty = { ...EMPTY_PAGE, owner: id };
    const [dx, rx, ev, pr] = await Promise.all([
      settle("diagnoses", () => loadPage<Diagnosis>(`${base}/diagnoses`, 0, id), empty),
      settle("remediations", () => loadPage<Remediation>(`${base}/remediations`, 0, id), empty),
      settle("workflow-events", () => loadPage<WorkflowEvent>(`${base}/workflow-events`, 0, id), empty),
      settle("knowledge-proposals", () => fetch(apiUrl(`${base}/knowledge-proposals`), { cache: "no-store" }).then(json), [] as ProposalLink[]),
    ]);
    if (token !== latest.current) return;
    setDiagnoses(dx); setRemediations(rx); setEvents(ev); setProposals(pr);
    if (secondaryErrors.length) setError(`Some workspace panels could not load. ${secondaryErrors.join("; ")}`);

    const ids = Array.from(new Set([...dx.items, ...rx.items].map((r) => r.knowledge?.catalog_id).filter(Boolean) as string[]));
    const fetched: Record<string, Current | null> = {};
    await Promise.all(ids.map(async (cid) => {
      try { fetched[cid] = await fetch(apiUrl(`/api/v1/analyzer/catalog/record?catalog_id=${encodeURIComponent(cid)}`), { cache: "no-store" }).then(json); }
      catch { fetched[cid] = null; }
    }));
    if (token === latest.current) setCurrent(fetched);
    if (pr.length > 0) {
      // Review state lives in Knowledge. Only the caller's own entries are visible here.
      try {
        const mine = await fetch(apiUrl("/api/v1/knowledge/proposals/mine?limit=100"), { cache: "no-store" }).then(json);
        const map: Record<number, string> = {};
        for (const item of mine.items || []) map[item.id] = item.status;
        if (token === latest.current) setProposalStatus(map);
      } catch { if (token === latest.current) setProposalStatus({}); }
    } else if (token === latest.current) setProposalStatus({});
  }, []);

  useEffect(() => { const t = window.setTimeout(() => { void loadDetail(incidentId); }, 0); return () => window.clearTimeout(t); }, [incidentId, loadDetail]);

  const more = async <T extends { [k: string]: unknown },>(
    kind: "diagnoses" | "remediations" | "workflow-events", idKey: string, page: Page<T>,
    set: (update: (prev: Page<T>) => Page<T>) => void,
  ) => {
    const forIncident = incidentId;
    try {
      const next = await loadPage<T>(`/api/v1/incidents/${forIncident}/${kind}`, page.items.length, forIncident);
      // Merge into the *current* list, and only if it still belongs to the incident that asked.
      set((prev) => {
        if (prev.owner !== forIncident) return prev;
        const seen = new Set(prev.items.map((x) => String(x[idKey])));
        const merged = [...prev.items, ...next.items.filter((x) => !seen.has(String(x[idKey])))];
        return { items: merged, total: next.total, exact: next.exact, hasMore: next.hasMore, owner: forIncident };
      });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load more"); }
  };

  const post = async (path: string, payload: unknown, ok: string) => {
    if (busy) return false;
    setBusy(true); setError(""); setMessage("");
    try {
      await json(await fetch(apiUrl(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }));
      await loadDetail(incidentId); // show the refreshed record first, then confirm
      setMessage(ok);
      onChanged?.({ incidentId });
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Request failed");
      return false;
    } finally { setBusy(false); }
  };

  const evidenceLabel = (id: string) => {
    const e = detail?.evidence.find((x) => x.evidence_id === id);
    return e ? `${e.source_type}:${e.source_id}` : id.slice(0, 8);
  };
  const more_btn = (page: Page<unknown>, onClick: () => void) => page.hasMore
    ? <button type="button" className={btn} onClick={onClick}>Load more (showing {page.items.length}{page.exact ? ` of ${page.total}` : ""})</button> : null;

  // ---- derived, data-backed summary (nothing here is invented) ----
  const open = detail ? !["resolved", "closed"].includes(detail.status) : false;
  const completed = detail ? !open : false;
  const confirmed = diagnoses.items.find((d) => d.status === "confirmed");
  const liveOpen = diagnoses.items.filter((d) => d.status === "hypothesis");
  const closedDx = diagnoses.items.filter((d) => ["rejected", "superseded"].includes(d.status));
  const liveOthers = (id: string) => diagnoses.items.filter((d) => d.diagnosis_id !== id && ["hypothesis", "confirmed"].includes(d.status));
  const headline = confirmed ?? (liveOpen.length ? liveOpen[liveOpen.length - 1] : null);
  const proposable = diagnoses.items.filter((d) => d.status === "confirmed" && d.analysis_history_id);
  const executed = remediations.items.filter((r) => r.status === "executed");
  const pendingRem = remediations.items.filter((r) => r.status === "proposed");
  const verifiedRem = remediations.items.filter((r) => r.verification_state === "verified");
  const catalogIds = Array.from(new Set([...diagnoses.items, ...remediations.items].map((r) => r.knowledge?.catalog_id).filter(Boolean) as string[]));
  const snapshots = [...diagnoses.items, ...remediations.items].map((r) => r.knowledge).filter(Boolean) as NonNullable<Snapshot>[];
  const knowledgeWarnings = [
    snapshots.some((s) => s.stale) || catalogIds.some((c) => current[c]?.classification.stale) ? "review stale" : "",
    snapshots.some((s) => s.overlay_available === false) ? "review state unavailable" : "",
    snapshots.some((s) => s.version_compatible === false) ? "version mismatch" : "",
    catalogIds.some((c) => { const snap = snapshots.find((s) => s.catalog_id === c); return current[c] && snap?.content_hash && current[c]?.content_hash !== snap.content_hash; }) ? "canonical content changed" : "",
  ].filter(Boolean);
  const evidenceSources = Array.from(new Set((detail?.evidence ?? []).map((e) => e.source_type)));
  const byAssurance = (level: string) => events.items.filter((e) => e.actor_assurance === level).length;

  const nextSteps: ReactNode[] = [];
  if (detail && open) {
    if (diagnoses.total === 0) nextSteps.push("Record a hypothesis and link the evidence that supports or contradicts it.");
    if (liveOpen.length > 0 && !confirmed) nextSteps.push("Review the open hypotheses. Confirming a root cause needs a verified reviewer and is not available from this open-access view.");
    if (pendingRem.length > 0) nextSteps.push(`Carry out or revise the proposed remediation: “${pendingRem[0].action}”.`);
    if (executed.some((r) => ["succeeded", "partial"].includes(r.outcome ?? "")) && verifiedRem.length === 0) nextSteps.push("Collect verification evidence for the executed remediation. Verification and resolution need a verified reviewer.");
  }
  if (detail && completed && confirmed && proposals.length === 0 && proposable.length > 0) nextSteps.push("Consider proposing knowledge from this incident; it enters the existing review process as pending.");
  const refSteps = catalogIds.flatMap((cid) => (current[cid]?.investigation_steps ?? []).slice(0, 3).map((s) => ({ cid, s, cls: current[cid]?.classification.classification })));

  return (
    <div className="space-y-4 min-w-0" data-testid="incident-workspace" aria-label="Incident Workspace">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="text-base font-semibold text-eims-text">
            {detail?.title || "Issue detail"}
          </h2>
          <p className="text-xs text-eims-text-muted">
            What happened and what to check next. AI suggestions are not confirmed facts.
            Confirming cause, verifying recovery, and resolving need a verified reviewer.
          </p>
        </div>
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close incident detail"
            title="Close incident detail"
            className="shrink-0 p-1.5 rounded-lg border border-eims-border text-eims-text-secondary hover:text-eims-text hover:bg-eims-bg">
            <X size={14} aria-hidden="true" />
          </button>)}
      </div>
      {error && <div role="alert" className="flex items-start gap-2 text-sm text-red-600 border border-red-500/30 rounded p-3"><AlertCircle size={16} className="mt-0.5" />{error}</div>}
      {message && <div role="status" className="text-sm text-emerald-700 dark:text-emerald-400 border border-emerald-500/30 rounded p-3">{message}</div>}
      {!detail ? <div className="bg-eims-surface border border-eims-border rounded-lg p-4"><p className="text-sm text-eims-text-muted">{error ? "The incident could not be loaded." : "Loading incident…"}</p></div> : (<>
            <section aria-label="Incident Overview" className="bg-eims-surface border border-eims-border rounded-lg p-4 space-y-3" data-testid="incident-overview">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={statusTone(detail.status)}>{incidentStatusLabel(detail.status)}</Badge>
                <Badge tone={severityTone(detail.severity)}>{detail.severity} severity</Badge>
                <Badge tone={rootTone(detail.root_cause_state)}>{rootCauseLabel(detail.root_cause_state)}</Badge>
                <span className="text-xs text-eims-text-muted font-mono" title="Incident identifier">{incidentId}</span>
                <span className="text-xs text-eims-text-muted">First seen {when(detail.first_seen)} · Updated {when(detail.updated_at ?? detail.last_seen)}</span>
              </div>
              <p className="text-sm text-eims-text-secondary" data-testid="incident-summary">
                <span className="font-medium text-eims-text">Overview: </span>
                {detail.evidence.length} linked evidence item{detail.evidence.length === 1 ? "" : "s"}
                {evidenceSources.length ? ` (${evidenceSources.join(", ")})` : ""}.
                Correlation confidence “{detail.confidence}” is evidence-association strength — not root-cause confidence.
                {detail.asset_id ? <> Asset/host id: <span className="font-mono text-xs">{detail.asset_id}</span>.</> : " Asset/host not resolved."}
                {detail.remediation_cycle > 0 ? ` Reopened — remediation cycle ${detail.remediation_cycle}.` : ""}
              </p>
              <p className="text-[11px] text-eims-text-muted">
                AI hypotheses are not confirmed causes. Fix applied is not Resolved. Resolved requires verification/reviewer rules from Incident Core.
              </p>

              <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                <div data-testid="glance-diagnosis">
                  <dt className="text-xs text-eims-text-muted">{confirmed ? "Confirmed root cause" : "Current diagnosis (latest open hypothesis)"}</dt>
                  <dd className="text-eims-text">
                    {headline ? (<>
                      <span className="block font-medium break-words">{headline.hypothesis}</span>
                      {headline.status === "confirmed"
                        ? <><Badge tone="good">Confirmed by {headline.confirmed_by}</Badge> <Assurance level={headline.confirmed_assurance} /></>
                        : <Badge tone="warn">{DIAGNOSIS_LABEL[headline.status]}</Badge>}
                      {liveOpen.length > 1 && !confirmed && <span className="ml-1 text-xs text-eims-text-secondary">+{liveOpen.length - 1} other open</span>}
                    </>) : <span className="text-eims-text-muted">None recorded</span>}
                  </dd>
                </div>
                <div data-testid="glance-remediation">
                  <dt className="text-xs text-eims-text-muted">Fix status</dt>
                  <dd className="text-eims-text">
                    {remediations.total === 0 ? <span className="text-eims-text-muted">None recorded</span>
                      : <>
                        {executed.length > 0 ? <Badge tone="warn">Fix applied</Badge> : null}
                        {" "}{executed.length} applied · {pendingRem.length} proposed{remediations.hasMore ? "+" : ""}
                        <span className="block text-xs text-eims-text-muted">Fix applied is not the same as Resolved.</span>
                        <span className="block text-xs text-eims-text-secondary break-words">Latest: {remediations.items[remediations.items.length - 1]?.action}</span>
                      </>}
                  </dd>
                </div>
                <div data-testid="glance-verification">
                  <dt className="text-xs text-eims-text-muted">Verification</dt>
                  <dd className="text-eims-text">
                    {detail.verifications.length > 0
                      ? <>Verified outcome recorded <span className="block text-xs text-eims-text-secondary">{detail.verifications.length} record{detail.verifications.length === 1 ? "" : "s"}, latest by {detail.verifications[detail.verifications.length - 1].verifier_id}</span></>
                      : verifiedRem.length > 0
                        ? <><Badge tone="good">Verified</Badge> <span className="text-xs text-eims-text-muted">(incident-level)</span></>
                        : executed.length > 0
                          ? <Badge tone="warn">Awaiting verification</Badge>
                          : <span className="text-eims-text-muted">Not verified</span>}
                  </dd>
                </div>
              </dl>

              {knowledgeWarnings.length > 0 && (
                <p className="text-xs text-amber-700 dark:text-amber-400" data-testid="knowledge-warning">
                  Knowledge warning: {knowledgeWarnings.join(" · ")} — see Diagnostic Knowledge Reference.
                </p>)}

              <div>
                <h3 className="text-xs font-semibold text-eims-text-muted uppercase tracking-wide">Next steps</h3>
                {nextSteps.length === 0 && refSteps.length === 0
                  ? <p className="text-sm text-eims-text-muted" data-testid="next-steps">No next action is indicated by the recorded data.</p>
                  : <ul className="mt-1 space-y-1 text-sm text-eims-text list-disc pl-5" data-testid="next-steps">
                    {nextSteps.map((s, i) => <li key={`n${i}`}>{s}</li>)}
                    {refSteps.slice(0, 4).map((r) => <li key={`${r.cid}-${r.s}`}>{r.s} <span className="text-xs text-eims-text-secondary">— Diagnostic Knowledge reference ({r.cls}), not a confirmed procedure</span></li>)}
                  </ul>}
              </div>
            </section>

            <section aria-label="Evidence and Timeline" className="bg-eims-surface border border-eims-border rounded-lg p-4 space-y-2" data-testid="sec-evidence-timeline">
              <h3 className="text-sm font-semibold text-eims-text">Evidence &amp; Timeline</h3>
              <p className="text-[11px] text-eims-text-muted">
                Observed_at below is the association/observation time from Incident Core. Event time from the original log is shown only when the linked analysis supplies it.
              </p>
              {detail.evidence.length === 0 ? (
                <p className="text-sm text-eims-text-muted">No evidence linked yet. Analyze a log and associate it, or wait for Incident Core to attach evidence.</p>
              ) : (
                <ul className="text-xs text-eims-text-secondary space-y-1.5">
                  {detail.evidence.map((e) => (
                    <li key={e.evidence_id} className="border-l-2 border-eims-border pl-2">
                      <span className="font-medium text-eims-text">{e.source_type}:{e.source_id}</span>
                      {e.source_event_key ? ` · ${e.source_event_key}` : ""}
                      <span className="block text-[11px]">Observed {when(e.observed_at)} (association time — not necessarily the original event clock)</span>
                      {e.source_type === "analysis" && /^\d+$/.test(e.source_id) ? (
                        <a
                          className="text-eims-accent hover:underline text-[11px]"
                          href={`/analyzer?analysis=${encodeURIComponent(e.source_id)}`}
                        >
                          Open Analysis Record Details
                        </a>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <EngineerNotes incidentId={incidentId} />

            <Disclosure title="Investigation Findings & Hypotheses" testId="sec-diagnosis" count={`${diagnoses.total} hypotheses`}
              status={<>{confirmed ? <Badge tone="good">Cause confirmed</Badge> : liveOpen.length ? <Badge tone="warn">{liveOpen.length} possible cause{liveOpen.length === 1 ? "" : "s"}</Badge> : null}{closedDx.length > 0 && <Badge>{closedDx.length} closed</Badge>}</>}>
              {diagnoses.items.length === 0 && !error.includes("diagnoses") && (
                <p className="text-sm text-eims-text-muted">
                  No supported hypothesis yet. EIMS needs additional evidence or a diagnostic match before proposing one — or record a hypothesis below if you have an observation-backed idea.
                </p>
              )}
              {diagnoses.items.length === 0 && error.includes("diagnoses") && (
                <p className="text-sm text-amber-700 dark:text-amber-400">Hypotheses could not be loaded. Use Retry from the alert above — this is not an empty investigation.</p>
              )}
              <ul className="space-y-2">
                {[...diagnoses.items.filter((d) => !["rejected", "superseded"].includes(d.status)), ...closedDx].map((d) => {
                  const form = closing[d.diagnosis_id];
                  const closed = ["rejected", "superseded"].includes(d.status);
                  return (
                    <li key={d.diagnosis_id} className={`rounded border border-eims-border p-3 ${closed ? "opacity-80" : ""}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={d.status === "confirmed" ? "good" : closed ? "neutral" : "warn"}>{DIAGNOSIS_LABEL[d.status] ?? d.status}</Badge>
                        <strong className="text-sm text-eims-text break-words">{d.hypothesis}</strong>
                        <span className="text-xs text-eims-text-secondary">stated confidence: {d.stated_confidence} (not proof)</span>
                      </div>
                      <Sub title="Details, provenance and actions">
                        {d.reasoning && <p className="text-sm text-eims-text-secondary">{d.reasoning}</p>}
                        <p className="text-xs text-eims-text-secondary">Proposed by {d.proposed_by} <Assurance level={d.proposed_assurance} long /> · {when(d.created_at)} · cycle {d.remediation_cycle}</p>
                        {d.confirmed_by && <p className="text-xs text-eims-text-secondary">Confirmed by {d.confirmed_by} <Assurance level={d.confirmed_assurance} long /> · {when(d.confirmed_at)}</p>}
                        {d.closed_by && <p className="text-xs text-eims-text-secondary">{DIAGNOSIS_LABEL[d.status]} by {d.closed_by} <Assurance level={d.closed_assurance} long /> · {when(d.closed_at)} — {d.closed_reason}{d.superseded_by_id ? ` (replaced by “${diagnoses.items.find((x) => x.diagnosis_id === d.superseded_by_id)?.hypothesis ?? d.superseded_by_id.slice(0, 8)}”)` : ""}</p>}
                        {d.supporting_evidence_ids.length > 0 && <p className="text-xs text-eims-text-secondary">Supporting evidence: {d.supporting_evidence_ids.map(evidenceLabel).join(", ")}</p>}
                        {d.contradicting_evidence_ids.length > 0 && <p className="text-xs text-eims-text-secondary">Contradicting evidence: {d.contradicting_evidence_ids.map(evidenceLabel).join(", ")}</p>}
                        {d.analysis_history_id && <p className="text-xs text-eims-text-secondary">Originating analysis #{d.analysis_history_id}</p>}
                        <KnowledgeLine snap={d.knowledge} current={d.knowledge ? current[d.knowledge.catalog_id] : null} />
                        {open && d.status === "hypothesis" && !form && (
                          <div className="flex gap-2">
                            <button type="button" className={btn} onClick={() => setClosing((c) => ({ ...c, [d.diagnosis_id]: { mode: "reject", reason: "", by: "" } }))}>Reject…</button>
                            <button type="button" className={btn} disabled={liveOthers(d.diagnosis_id).length === 0}
                              onClick={() => setClosing((c) => ({ ...c, [d.diagnosis_id]: { mode: "supersede", reason: "", by: liveOthers(d.diagnosis_id)[0]?.diagnosis_id ?? "" } }))}>Supersede…</button>
                          </div>)}
                        {form && (
                          <form className="space-y-1" onSubmit={async (e) => {
                            e.preventDefault();
                            const ok = await post(`/api/v1/incidents/${incidentId}/diagnoses/${d.diagnosis_id}/${form.mode}`,
                              form.mode === "reject" ? { reason: form.reason } : { reason: form.reason, superseded_by_id: form.by },
                              form.mode === "reject" ? "Hypothesis rejected; its history is kept." : "Hypothesis superseded; its history is kept.");
                            if (ok) setClosing((c) => { const n = { ...c }; delete n[d.diagnosis_id]; return n; });
                          }}>
                            <label className="block text-xs text-eims-text-secondary" htmlFor={`why-${d.diagnosis_id}`}>Reason</label>
                            <input id={`why-${d.diagnosis_id}`} className={field} required maxLength={4000} value={form.reason}
                              onChange={(e) => setClosing((c) => ({ ...c, [d.diagnosis_id]: { ...form, reason: e.target.value } }))} />
                            {form.mode === "supersede" && (<>
                              <label className="block text-xs text-eims-text-secondary" htmlFor={`by-${d.diagnosis_id}`}>Replaced by</label>
                              <select id={`by-${d.diagnosis_id}`} className={field} value={form.by}
                                onChange={(e) => setClosing((c) => ({ ...c, [d.diagnosis_id]: { ...form, by: e.target.value } }))}>
                                {liveOthers(d.diagnosis_id).map((o) => <option key={o.diagnosis_id} value={o.diagnosis_id}>{o.hypothesis}</option>)}
                              </select></>)}
                            <div className="flex gap-2">
                              <button type="submit" disabled={busy} className={btn}>{form.mode === "reject" ? "Reject hypothesis" : "Supersede hypothesis"}</button>
                              <button type="button" className={btn} onClick={() => setClosing((c) => { const n = { ...c }; delete n[d.diagnosis_id]; return n; })}>Cancel</button>
                            </div>
                          </form>)}
                      </Sub>
                    </li>);
                })}
              </ul>
              {more_btn(diagnoses, () => more("diagnoses", "diagnosis_id", diagnoses, setDiagnoses))}
              {open && (
                <Sub title="Record a hypothesis">
                  <form className="space-y-2" onSubmit={async (e) => {
                    e.preventDefault();
                    const ok = await post(`/api/v1/incidents/${incidentId}/diagnoses`, {
                      hypothesis, reasoning, stated_confidence: confidence, supporting_evidence_ids: supporting,
                      ...(catalogId.trim() ? { catalog_id: catalogId.trim() } : {}),
                      ...(refAnalysis && analysisHistoryId ? { analysis_history_id: analysisHistoryId } : {}),
                    }, "Hypothesis recorded (unattributed unless a verified credential was used).");
                    if (ok) { setHypothesis(""); setReasoning(""); setSupporting([]); setCatalogId(""); }
                  }}>
                    <label className="block text-xs text-eims-text-secondary" htmlFor="hyp">Hypothesis</label>
                    <input id="hyp" className={field} value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} maxLength={1000} required />
                    <label className="block text-xs text-eims-text-secondary" htmlFor="why">Reasoning</label>
                    <textarea id="why" className={field} rows={2} value={reasoning} onChange={(e) => setReasoning(e.target.value)} maxLength={8000} />
                    <label className="block text-xs text-eims-text-secondary" htmlFor="conf">Stated confidence (not proof)</label>
                    <select id="conf" className={field} value={confidence} onChange={(e) => setConfidence(e.target.value)}>
                      <option value="low">low</option><option value="medium">medium</option><option value="high">high</option>
                    </select>
                    <fieldset className="text-xs text-eims-text-secondary">
                      <legend>Supporting evidence</legend>
                      {detail.evidence.map((e) => (
                        <label key={e.evidence_id} className="block">
                          <input type="checkbox" checked={supporting.includes(e.evidence_id)} onChange={(ev) =>
                            setSupporting((cur) => ev.target.checked ? [...cur, e.evidence_id] : cur.filter((x) => x !== e.evidence_id))} />{" "}
                          {e.source_type}:{e.source_id}
                        </label>))}
                    </fieldset>
                    <label className="block text-xs text-eims-text-secondary" htmlFor="cat">Diagnostic Knowledge catalog id (optional; trust is looked up by the server)</label>
                    <input id="cat" className={field} value={catalogId} onChange={(e) => setCatalogId(e.target.value)} maxLength={200} />
                    {analysisHistoryId ? (
                      <label className="block text-xs text-eims-text-secondary">
                        <input type="checkbox" checked={refAnalysis} onChange={(e) => setRefAnalysis(e.target.checked)} />{" "}
                        Reference the selected analysis (#{analysisHistoryId}); a knowledge proposal later needs this link
                      </label>) : null}
                    <button type="submit" disabled={busy} className={btn}>Record hypothesis</button>
                  </form>
                </Sub>)}
            </Disclosure>

            <Disclosure title="Remediation & Rollback" testId="sec-remediation" count={remediations.total}
              status={<>{pendingRem.length > 0 && <Badge tone="warn">{pendingRem.length} proposed</Badge>}{executed.length > 0 && <Badge tone="info">{executed.length} executed</Badge>}</>}>
              {remediations.items.length === 0 && <p className="text-sm text-eims-text-muted">No remediation recorded.</p>}
              <ul className="space-y-2">
                {remediations.items.map((r) => {
                  const form = exec[r.remediation_id] ?? { actual_action: "", outcome: "succeeded", outcome_notes: "" };
                  return (
                    <li key={r.remediation_id} className="rounded border border-eims-border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <strong className="text-sm text-eims-text break-words">{r.action}</strong>
                        <Badge tone={r.status === "executed" ? "info" : "warn"}>{r.status === "executed" ? `Executed: ${r.outcome}` : "Proposed · not executed"}</Badge>
                        <Badge tone={r.verification_state === "verified" ? "good" : "neutral"}>{r.verification_state === "verified" ? "verified (incident-level)" : "not verified"}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-eims-text-secondary" data-testid="guidance-basis">
                        {r.knowledge?.canonical_remediation_available
                          ? "Canonical remediation guidance exists for the referenced catalog record."
                          : r.catalog_id
                            ? "Incident-specific action. The referenced catalog record has no canonical remediation guidance."
                            : "Incident-specific action. No catalog record is referenced. It is not approved reusable knowledge."}
                      </p>
                      <Sub title="Risk, rollback, verification criteria and provenance">
                        <p className="text-xs text-eims-text-secondary">Risk: {r.risk}</p>
                        {r.impact && <p className="text-xs text-eims-text-secondary">Impact: {r.impact}</p>}
                        <p className="text-xs text-eims-text-secondary">Rollback plan: {r.rollback_plan}</p>
                        <p className="text-xs text-eims-text-secondary">Expected verification: {r.expected_verification_criteria}</p>
                        <p className="text-xs text-eims-text-secondary">Proposed by {r.proposed_by} <Assurance level={r.proposed_assurance} long /> · {when(r.created_at)}</p>
                        {r.status === "executed" && (<>
                          <p className="text-xs text-eims-text-secondary">Done: {r.actual_action}{r.outcome_notes ? ` — ${r.outcome_notes}` : ""}</p>
                          <p className="text-xs text-eims-text-secondary">Executed by {r.executed_by} <Assurance level={r.executed_assurance} long /> · {when(r.executed_at)}</p>
                        </>)}
                        <KnowledgeLine snap={r.knowledge} current={r.knowledge ? current[r.knowledge.catalog_id] : null} />
                        {open && r.status === "proposed" && (
                          <form className="space-y-1" onSubmit={async (e) => {
                            e.preventDefault();
                            const ok = await post(`/api/v1/incidents/${incidentId}/remediations/${r.remediation_id}/execution`, form, "Execution recorded. It is not a verification.");
                            if (ok) setExec((cur) => { const n = { ...cur }; delete n[r.remediation_id]; return n; });
                          }}>
                            <label className="block text-xs text-eims-text-secondary" htmlFor={`act-${r.remediation_id}`}>What was actually done</label>
                            <input id={`act-${r.remediation_id}`} className={field} required maxLength={4000} value={form.actual_action}
                              onChange={(e) => setExec((cur) => ({ ...cur, [r.remediation_id]: { ...form, actual_action: e.target.value } }))} />
                            <label className="block text-xs text-eims-text-secondary" htmlFor={`out-${r.remediation_id}`}>Outcome</label>
                            <select id={`out-${r.remediation_id}`} className={field} value={form.outcome}
                              onChange={(e) => setExec((cur) => ({ ...cur, [r.remediation_id]: { ...form, outcome: e.target.value } }))}>
                              {OUTCOMES.map((o) => <option key={o} value={o}>{o}</option>)}
                            </select>
                            <label className="block text-xs text-eims-text-secondary" htmlFor={`nt-${r.remediation_id}`}>Notes</label>
                            <input id={`nt-${r.remediation_id}`} className={field} maxLength={4000} value={form.outcome_notes}
                              onChange={(e) => setExec((cur) => ({ ...cur, [r.remediation_id]: { ...form, outcome_notes: e.target.value } }))} />
                            <button type="submit" disabled={busy} className={btn}>Record execution</button>
                          </form>)}
                      </Sub>
                    </li>);
                })}
              </ul>
              {more_btn(remediations, () => more("remediations", "remediation_id", remediations, setRemediations))}
              {open && (
                <Sub title="Propose a remediation">
                  <form className="space-y-2" onSubmit={async (e) => {
                    e.preventDefault();
                    const { catalog_id, ...rest } = rem;
                    const ok = await post(`/api/v1/incidents/${incidentId}/remediations`,
                      { ...rest, ...(catalog_id.trim() ? { catalog_id: catalog_id.trim() } : {}) },
                      "Remediation proposed. It has not been executed or verified.");
                    if (ok) setRem({ action: "", risk: "", rollback_plan: "", expected_verification_criteria: "", impact: "", catalog_id: "" });
                  }}>
                    {([["action", "Action"], ["risk", "Risk"], ["rollback_plan", "Rollback plan"],
                       ["expected_verification_criteria", "How recovery will be verified"], ["impact", "Impact (optional)"],
                       ["catalog_id", "Diagnostic Knowledge catalog id (optional)"]] as const).map(([key, label]) => (
                      <div key={key}>
                        <label className="block text-xs text-eims-text-secondary" htmlFor={`rem-${key}`}>{label}</label>
                        <input id={`rem-${key}`} className={field} value={rem[key]} required={!["impact", "catalog_id"].includes(key)} maxLength={key === "action" ? 1000 : key === "catalog_id" ? 200 : 4000}
                          onChange={(e) => setRem((cur) => ({ ...cur, [key]: e.target.value }))} />
                      </div>))}
                    <button type="submit" disabled={busy} className={btn}>Propose remediation</button>
                  </form>
                </Sub>)}
            </Disclosure>

            <Disclosure title="Verification" testId="sec-verification" count={detail.verifications.length}
              status={detail.verifications.length > 0 ? <Badge tone="good">recorded</Badge> : <Badge>none</Badge>}>
              {detail.verifications.length === 0
                ? <p className="text-sm text-eims-text-muted">No verification records. Verification and resolution need a verified reviewer.</p>
                : <ul className="text-xs text-eims-text-secondary space-y-1">
                  {detail.verifications.map((v) => <li key={v.verification_id}>Cycle {v.remediation_cycle}: {v.outcome} by {v.verifier_id} · {when(v.verified_at)}</li>)}
                </ul>}
              <p className="text-xs text-eims-text-secondary">A remediation shows “verified” only when a passed verification of its cycle was recorded after a succeeded execution; it is an incident-level signal.</p>
            </Disclosure>

            <Disclosure title="Diagnostic Knowledge Reference" testId="sec-knowledge" count={catalogIds.length}
              status={knowledgeWarnings.length > 0 ? <Badge tone="warn">{knowledgeWarnings[0]}{knowledgeWarnings.length > 1 ? ` +${knowledgeWarnings.length - 1}` : ""}</Badge> : catalogIds.length ? <Badge>no warnings</Badge> : <Badge>none linked</Badge>}>
              {catalogIds.length === 0 && <p className="text-sm text-eims-text-muted">No catalog record is linked to this incident.</p>}
              {catalogIds.map((cid) => {
                const snap = snapshots.find((s) => s.catalog_id === cid) ?? null;
                return (
                  <div key={cid} className="text-sm space-y-1">
                    <div className="font-medium text-eims-text break-all">{cid}</div>
                    <KnowledgeLine snap={snap} current={current[cid]} />
                    {current[cid] === null && <p className="text-xs text-amber-700 dark:text-amber-400">The current canonical record could not be loaded.</p>}
                  </div>);
              })}
              <p className="text-xs text-eims-text-secondary">The first line is the historical snapshot taken when the incident used the record. It is never rewritten. The second line is today’s canonical record.</p>
            </Disclosure>

            <Disclosure title="Knowledge Proposal" testId="sec-proposal" count={proposals.length}
              status={proposals.length === 0 ? <Badge>{completed ? "none submitted" : "after completion"}</Badge>
                : proposals.map((p) => <Badge key={p.proposal_link_id} tone={proposalStatus[p.knowledge_entry_id] === "approved" ? "good" : "warn"}>{proposalStatus[p.knowledge_entry_id] ?? "status unavailable here"}</Badge>)}>
              <p className="text-xs text-eims-text-secondary">
                A proposal enters the existing Knowledge review process as <strong>pending</strong>; it is not trusted knowledge until an independent reviewer approves it.
                Incident findings are never promoted automatically. <Link className="underline" href="/knowledge">Open Knowledge review</Link>
              </p>
              {proposals.length > 0 && (
                <ul className="text-xs text-eims-text-secondary space-y-1">
                  {proposals.map((p) => (
                    <li key={p.proposal_link_id}>
                      Knowledge entry #{p.knowledge_entry_id} · review state: <strong>{proposalStatus[p.knowledge_entry_id] ?? "unavailable from this view (shown for the proposer’s own entries; see Knowledge review)"}</strong>
                      {" "}· proposed by {p.proposed_by} <Assurance level={p.proposed_assurance} long /> · {when(p.created_at)}
                    </li>))}
                </ul>)}
              {!completed ? <p className="text-sm text-eims-text-muted">Available once the incident is resolved and has a confirmed root cause.</p>
                : proposable.length === 0 ? <p className="text-sm text-eims-text-muted">A proposal needs a root cause confirmed by a verified reviewer that references the analysis it came from.</p>
                : (
                  <Sub title="Submit a proposal for review">
                    <form className="space-y-2" onSubmit={async (e) => {
                      e.preventDefault();
                      const ok = await post(`/api/v1/incidents/${incidentId}/knowledge-proposals`, {
                        diagnosis_id: kp.diagnosis || proposable[0].diagnosis_id,
                        ...(kp.remediation ? { remediation_id: kp.remediation } : {}),
                        evidence_ids: proposable.find((d) => d.diagnosis_id === (kp.diagnosis || proposable[0].diagnosis_id))?.supporting_evidence_ids ?? [],
                        proposal: {
                          title: kp.title, resolution_status: kp.resolution, root_cause: kp.root_cause, solution_steps: lines(kp.steps),
                          evidence_notes: lines(kp.evidence), validation_steps: lines(kp.validation), rollback_steps: lines(kp.rollback), risk_level: kp.risk,
                        },
                      }, "Knowledge proposal submitted as pending for independent review.");
                      if (ok) setKp({ title: "", root_cause: "", steps: "", evidence: "", validation: "", rollback: "", resolution: "resolved", risk: "medium", diagnosis: "", remediation: "" });
                    }}>
                      <label className="block text-xs text-eims-text-secondary" htmlFor="kp-dx">Confirmed diagnosis</label>
                      <select id="kp-dx" className={field} value={kp.diagnosis || proposable[0].diagnosis_id} onChange={(e) => setKp({ ...kp, diagnosis: e.target.value })}>
                        {proposable.map((d) => <option key={d.diagnosis_id} value={d.diagnosis_id}>{d.hypothesis}</option>)}
                      </select>
                      <label className="block text-xs text-eims-text-secondary" htmlFor="kp-rem">Executed remediation (optional)</label>
                      <select id="kp-rem" className={field} value={kp.remediation} onChange={(e) => setKp({ ...kp, remediation: e.target.value })}>
                        <option value="">none</option>
                        {executed.map((r) => <option key={r.remediation_id} value={r.remediation_id}>{r.action}</option>)}
                      </select>
                      {([["title", "Title", false], ["root_cause", "Root cause", false], ["steps", "Resolution steps (one per line)", true],
                         ["evidence", "Evidence notes (one per line)", true], ["validation", "Validation steps (one per line)", true],
                         ["rollback", "Rollback steps (one per line)", true]] as const).map(([key, label, multi]) => (
                        <div key={key}>
                          <label className="block text-xs text-eims-text-secondary" htmlFor={`kp-${key}`}>{label}</label>
                          {multi ? <textarea id={`kp-${key}`} className={field} rows={2} value={kp[key]} onChange={(e) => setKp({ ...kp, [key]: e.target.value })} />
                            : <input id={`kp-${key}`} className={field} value={kp[key]} onChange={(e) => setKp({ ...kp, [key]: e.target.value })} />}
                        </div>))}
                      <label className="block text-xs text-eims-text-secondary" htmlFor="kp-risk">Risk level</label>
                      <select id="kp-risk" className={field} value={kp.risk} onChange={(e) => setKp({ ...kp, risk: e.target.value })}>
                        {["low", "medium", "high", "critical"].map((v) => <option key={v} value={v}>{v}</option>)}
                      </select>
                      <button type="submit" disabled={busy} className={btn}>Submit proposal for review</button>
                    </form>
                  </Sub>)}
            </Disclosure>

            <Disclosure title="Audit Trail" testId="sec-audit" count={events.exact ? events.total : events.items.length}
              status={<>{byAssurance("unattributed") > 0 && <Badge tone="warn">{byAssurance("unattributed")} unattributed</Badge>}{byAssurance("shared-token") > 0 && <Badge tone="warn">{byAssurance("shared-token")} shared token</Badge>}{byAssurance("verified-identity") > 0 && <Badge tone="good">{byAssurance("verified-identity")} verified</Badge>}</>}>
              <p className="text-xs text-eims-text-secondary">Append-only history of diagnosis and remediation activity with the actor and assurance of every action.</p>
              {events.items.length === 0 ? <p className="text-sm text-eims-text-muted">No diagnosis or remediation activity yet.</p>
                : <ul className="text-xs text-eims-text-secondary space-y-1">
                  {events.items.map((e) => <li key={e.event_id}>{when(e.created_at)} — {e.record_type} {e.action} by {e.actor} <Assurance level={e.actor_assurance} /></li>)}
                </ul>}
              {more_btn(events, () => more("workflow-events", "event_id", events, setEvents))}
            </Disclosure>
      </>)}
    </div>
  );
}
