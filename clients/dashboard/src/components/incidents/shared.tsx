"use client";

/**
 * Shared types, helpers and small presentational pieces for the Incident Workspace.
 * Presentation only: no business rule lives here (authorization stays in the backend domain service).
 */
import type { ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import { apiUrl } from "@/lib/api";

export type Incident = {
  incident_id: string; title: string; status: string; severity: string; confidence: string;
  root_cause_state: string; remediation_cycle: number; first_seen: string; last_seen: string; updated_at?: string;
  asset_id?: string | null;
};
export type Evidence = { evidence_id: string; source_type: string; source_id: string; source_event_key?: string | null; observed_at: string };
export type Verification = { verification_id: string; remediation_cycle: number; outcome: string; verifier_id: string; verified_at: string };
export type Detail = Incident & { evidence: Evidence[]; verifications: Verification[] };
export type Snapshot = {
  catalog_id: string; classification: string; lifecycle_status?: string | null; stale?: boolean;
  overlay_available?: boolean; version_scope?: string | null; version_compatible?: boolean | null;
  content_hash?: string; captured_at?: string; canonical_remediation_available?: boolean;
} | null;
export type Diagnosis = {
  diagnosis_id: string; remediation_cycle: number; hypothesis: string; reasoning: string;
  stated_confidence: string; status: string; supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[]; knowledge: Snapshot; analysis_history_id?: number | null;
  proposed_by: string; proposed_assurance: string; confirmed_by?: string | null;
  confirmed_assurance?: string | null; confirmed_at?: string | null; closed_by?: string | null;
  closed_assurance?: string | null; closed_reason?: string | null; closed_at?: string | null;
  superseded_by_id?: string | null; created_at: string;
};
export type Remediation = {
  remediation_id: string; diagnosis_id?: string | null; remediation_cycle: number; action: string;
  risk: string; impact: string; rollback_plan: string; expected_verification_criteria: string;
  status: string; proposed_by: string; proposed_assurance: string; executed_by?: string | null;
  executed_assurance?: string | null; executed_at?: string | null; actual_action?: string | null;
  outcome?: string | null; outcome_notes?: string | null; verification_state: string;
  catalog_id?: string | null; knowledge: Snapshot; created_at: string;
};
export type WorkflowEvent = { event_id: string; record_type: string; action: string; actor: string; actor_assurance: string; created_at: string };
export type ProposalLink = { proposal_link_id: string; knowledge_entry_id: number; diagnosis_id: string; proposed_by: string; proposed_assurance: string; created_at: string };
export type Current = {
  content_hash: string; investigation_steps?: string[];
  classification: { classification: string; stale?: boolean; overlayAvailable?: boolean };
};
export type Page<T> = { items: T[]; total: number; exact: boolean; hasMore: boolean; owner: string };

export const PAGE = 50;
export const EMPTY_PAGE = { items: [], total: 0, exact: true, hasMore: false, owner: "" };
export const ASSURANCE_SHORT: Record<string, string> = {
  "unattributed": "Unattributed", "shared-token": "Shared token", "verified-identity": "Verified identity",
};
export const ASSURANCE_LONG: Record<string, string> = {
  "unattributed": "Unattributed: open access, the individual is not proven",
  "shared-token": "Shared token: a shared secret, not a proven person",
  "verified-identity": "Verified identity",
};
export const OUTCOMES = ["succeeded", "failed", "partial", "rolled_back"] as const;
export const DIAGNOSIS_LABEL: Record<string, string> = {
  hypothesis: "Hypothesis · not confirmed", confirmed: "Confirmed root cause", rejected: "Rejected", superseded: "Superseded",
};

export async function json(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return body;
}

export async function loadPage<T>(path: string, offset: number, owner: string): Promise<Page<T>> {
  const sep = path.includes("?") ? "&" : "?";
  const response = await fetch(apiUrl(`${path}${sep}limit=${PAGE}&offset=${offset}`), { cache: "no-store" });
  const items = await json(response);
  const header = response.headers.get("X-Total-Count");
  // If a proxy drops the total, a full page still means there may be more.
  const total = header !== null ? Number(header) : items.length + (items.length === PAGE ? 1 : 0);
  return { items, total, exact: header !== null, hasMore: header !== null ? offset + items.length < total : items.length === PAGE, owner };
}

export const field = "w-full bg-eims-bg border border-eims-border rounded px-2 py-1.5 text-sm text-eims-text";
export const btn = "px-3 py-1.5 text-sm rounded border border-eims-info text-eims-info disabled:opacity-50";
export const lines = (value: string) => value.split("\n").map((v) => v.trim()).filter(Boolean);
export const when = (value?: string | null) => (value ? new Date(value).toLocaleString() : "—");

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "warn" | "good" | "info"; title?: string }) {
  const tones = {
    neutral: "border-eims-border text-eims-text-secondary",
    warn: "border-amber-500/40 text-amber-700 dark:text-amber-400",
    good: "border-emerald-500/40 text-emerald-700 dark:text-emerald-400",
    info: "border-sky-500/40 text-sky-700 dark:text-sky-400",
  };
  return <span title={title} className={`inline-block text-[11px] leading-5 px-2 rounded border ${tones[tone]}`}>{children}</span>;
}

/** Short, always-visible assurance label. The text itself carries the distinction (not colour alone). */
export function Assurance({ level, long = false }: { level?: string | null; long?: boolean }) {
  if (!level) return null;
  return <Badge tone={level === "verified-identity" ? "good" : "warn"} title={ASSURANCE_LONG[level]}>{long ? (ASSURANCE_LONG[level] ?? level) : (ASSURANCE_SHORT[level] ?? level)}</Badge>;
}

export const statusTone = (s: string) => (["resolved", "closed"].includes(s) ? "good" : "info") as "good" | "info";
export const severityTone = (s: string) => (["high", "critical"].includes(s) ? "warn" : "neutral") as "warn" | "neutral";
export const rootTone = (s: string) => (s === "confirmed" ? "good" : s === "hypothesis" ? "warn" : "neutral") as "good" | "warn" | "neutral";

/** Native <details>: keyboard accessible, expanded state announced by the browser. */
export function Disclosure({ title, status, count, defaultOpen = false, children, testId }: {
  title: string; status?: ReactNode; count?: number | string; defaultOpen?: boolean; children: ReactNode; testId?: string;
}) {
  return (
    <details open={defaultOpen} className="group bg-eims-surface border border-eims-border rounded-lg" data-testid={testId}>
      <summary className="flex flex-wrap items-center gap-2 px-4 py-3 cursor-pointer list-none select-none rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-eims-info">
        <ChevronRight size={16} className="text-eims-text-secondary transition-transform group-open:rotate-90" aria-hidden="true" />
        <span className="text-sm font-semibold text-eims-text">{title}</span>
        {count !== undefined && <span className="text-xs text-eims-text-secondary">({count})</span>}
        {status && <span className="ml-auto flex flex-wrap items-center gap-1">{status}</span>}
      </summary>
      <div className="px-4 pb-4 pt-1 space-y-3 border-t border-eims-border">{children}</div>
    </details>
  );
}

export function Sub({ title, children, open = false }: { title: ReactNode; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group/sub">
      <summary className="cursor-pointer text-xs text-eims-info select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-eims-info rounded">{title}</summary>
      <div className="mt-2 space-y-2">{children}</div>
    </details>
  );
}

export function KnowledgeLine({ snap, current }: { snap: Snapshot; current?: Current | null }) {
  if (!snap) return null;
  const changed = current && snap.content_hash && current.content_hash !== snap.content_hash;
  return (
    <div className="text-xs text-eims-text-secondary space-y-0.5" data-testid="knowledge-snapshot">
      <div>
        <strong>Recorded at the time</strong>: {snap.catalog_id} — <strong>{snap.classification}</strong>
        {snap.stale ? " · review stale" : ""}{snap.overlay_available === false ? " · review state unavailable" : ""}
        {snap.version_compatible === false ? " · different product version" : ""}
        {snap.version_scope ? ` · version scope ${snap.version_scope}` : ""}
        {snap.captured_at ? ` · ${when(snap.captured_at)}` : ""}
      </div>
      {current && (
        <div data-testid="knowledge-current">
          <strong>Current canonical record</strong>: {current.classification.classification}
          {current.classification.stale ? " · review stale" : ""}
          {changed ? " — canonical content has changed since it was recorded." : " — content unchanged since."}
        </div>)}
    </div>
  );
}
