"use client";

import { useEffect, useState, type ReactNode } from "react";

type InfraStatus = "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | "UNKNOWN" | "NOT_ENABLED";

type ServiceProbe = {
  status: InfraStatus;
  enableHint?: string;
};

type InfraStatusPayload = {
  services?: {
    grafana?: ServiceProbe;
    prometheus?: ServiceProbe;
  };
};

type Props = {
  service: "grafana" | "prometheus";
  href: string;
  className: string;
  children: ReactNode;
  /** Compact sidebar vs home card copy */
  variant?: "nav" | "card";
};

/**
 * When Observability profile is off, show NOT_ENABLED instead of a dead external link.
 */
export function OptionalInfraLink({ service, href, className, children, variant = "nav" }: Props) {
  const [probe, setProbe] = useState<ServiceProbe | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch("/api/infra-status", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as InfraStatusPayload;
        if (!cancelled) setProbe(data.services?.[service] ?? null);
      } catch {
        /* leave null — fall through to link */
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [service]);

  if (probe?.status === "NOT_ENABLED") {
    const hint = probe.enableHint || "start_eims_observability.bat";
    if (variant === "card") {
      return (
        <div
          className={`${className} opacity-70 cursor-default`}
          title={hint}
          role="status"
          aria-label={`${service} not enabled`}
        >
          {children}
          <p className="text-[10px] text-eims-text-muted mt-1 px-0">NOT_ENABLED — {hint}</p>
        </div>
      );
    }
    return (
      <span
        className={`${className} opacity-60 cursor-default`}
        title={hint}
        role="status"
        aria-label={`${service} not enabled`}
      >
        {children}
        <span className="ml-auto text-[10px] uppercase text-eims-text-muted">off</span>
      </span>
    );
  }

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
    </a>
  );
}
