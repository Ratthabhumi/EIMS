"use client";

import { ScrollText, Activity, Terminal, ShieldAlert, AlertTriangle, Info, CheckCircle2, FileSearch, BadgeCheck, GitBranch } from "lucide-react";

export type TimelineEventType =
  | "audit"
  | "incident_transition"
  | "evidence"
  | "verification"
  | "telemetry"
  | "winlog";

export interface TimelineEventData {
  id: string;
  type: TimelineEventType | string;
  title: string;
  description: string;
  severity: string;
  timestamp: string;
  actor_id: string | null;
  entity_id: string | null;
  entity_type: string;
  metadata: Record<string, unknown>;
}

const TYPE_META: Record<string, { label: string; icon: typeof ScrollText; classes: string }> = {
  audit: {
    label: "Audit",
    icon: ScrollText,
    classes: "text-eims-secondary bg-eims-secondary/10 border-eims-secondary/20",
  },
  incident_transition: {
    label: "Incident",
    icon: GitBranch,
    classes: "text-violet-500 bg-violet-500/10 border-violet-500/20",
  },
  evidence: {
    label: "Evidence",
    icon: FileSearch,
    classes: "text-cyan-500 bg-cyan-500/10 border-cyan-500/20",
  },
  verification: {
    label: "Verification",
    icon: BadgeCheck,
    classes: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20",
  },
  telemetry: {
    label: "Telemetry",
    icon: Activity,
    classes: "text-eims-info bg-eims-info/10 border-eims-info/20",
  },
  winlog: {
    label: "WinLog",
    icon: Terminal,
    classes: "text-eims-warning bg-eims-warning/10 border-eims-warning/20",
  },
};

const SEVERITY_META: Record<string, { label: string; icon: typeof AlertTriangle; classes: string }> = {
  Critical: {
    label: "Critical",
    icon: ShieldAlert,
    classes: "text-eims-error bg-eims-error/10 border-eims-error/20",
  },
  Warning: {
    label: "Warning",
    icon: AlertTriangle,
    classes: "text-eims-warning bg-eims-warning/10 border-eims-warning/20",
  },
  Information: {
    label: "Information",
    icon: Info,
    classes: "text-eims-success bg-eims-success/10 border-eims-success/20",
  },
};

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function metaString(metadata: Record<string, unknown>, key: string): string | null {
  const value = metadata[key];
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  return null;
}

export function TimelineEvent({ event }: { event: TimelineEventData }) {
  const typeMeta = TYPE_META[event.type] ?? {
    label: event.type ?? "Event",
    icon: CheckCircle2,
    classes: "text-eims-text-muted bg-eims-surface-subtle border-eims-border",
  };
  const severityMeta = SEVERITY_META[event.severity] ?? {
    label: event.severity ?? "Unknown",
    icon: CheckCircle2,
    classes: "text-eims-text-muted bg-eims-surface-subtle border-eims-border",
  };
  const TypeIcon = typeMeta.icon;
  const SeverityIcon = severityMeta.icon;

  const assurance = metaString(event.metadata, "assurance");
  const principal = metaString(event.metadata, "principal");
  const actorRaw =
    metaString(event.metadata, "actor") ||
    (event.actor_id ? event.actor_id : null);
  const actorLabel = (() => {
    if (assurance === "unattributed") {
      return principal ? `unattributed (${principal})` : "unattributed";
    }
    if (assurance === "shared_token") {
      return principal ? `shared-token (${principal})` : "shared-token";
    }
    if (assurance === "historical_unavailable") {
      return "not available in historical source";
    }
    if (assurance === "verified_identity" && actorRaw) return actorRaw;
    return actorRaw;
  })();
  const incidentId = metaString(event.metadata, "incident_id");
  const correlationId = metaString(event.metadata, "correlation_id");
  const corrLabel =
    correlationId ??
    (assurance === "historical_unavailable" ? "not available in historical source" : null);

  return (
    <article className="surface-card p-4 flex items-start gap-3 hover:border-eims-accent/60 transition-colors">
      <div className="w-9 h-9 rounded-md bg-eims-surface-subtle border border-eims-border flex items-center justify-center shrink-0">
        <TypeIcon className="w-4 h-4 text-eims-text-secondary" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span
            className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide rounded border ${typeMeta.classes}`}
          >
            {typeMeta.label}
          </span>
          <span
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border ${severityMeta.classes}`}
          >
            <SeverityIcon className="w-3 h-3" />
            {severityMeta.label}
          </span>
        </div>

        <h3 className="text-sm font-medium text-eims-text mt-1.5 break-words">{event.title}</h3>

        {event.description ? (
          <p className="text-xs text-eims-text-secondary mt-0.5 break-words">{event.description}</p>
        ) : null}

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-xs text-eims-text-muted">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            <time dateTime={event.timestamp}>{formatTimestamp(event.timestamp)}</time>
          </span>
          <span className="inline-flex items-center gap-1 font-mono truncate max-w-[220px]">
            asset {event.entity_id ?? "unavailable"}
          </span>
          <span className="inline-flex items-center gap-1 font-mono truncate max-w-[220px]" title={assurance || undefined}>
            actor {actorLabel ?? "unavailable"}
          </span>
          <span className="inline-flex items-center gap-1 font-mono truncate max-w-[220px]">
            incident {incidentId ?? "unavailable"}
          </span>
          <span className="inline-flex items-center gap-1 font-mono truncate max-w-[220px]">
            corr {corrLabel ?? "unavailable"}
          </span>
        </div>
      </div>
    </article>
  );
}
