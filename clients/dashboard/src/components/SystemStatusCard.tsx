"use client";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useHealthStatus } from "@/lib/health-monitor";

type Status = "ok" | "error" | "loading";

interface ServiceStatus {
  name: string;
  status: Status;
}

export default function SystemStatusCard() {
  const health = useHealthStatus();
  const services: ServiceStatus[] = [
    { name: "API Server", status: health === null ? "loading" : health.apiReachable ? "ok" : "error" },
    { name: "Database", status: health === null ? "loading" : health.components.postgresql_pgbouncer_tier === "UP" ? "ok" : "error" },
    { name: "Cache / Redis", status: health === null ? "loading" : health.components.redis_volatile_lru_tier === "UP" ? "ok" : "error" },
  ];
  const allOk = services.every((s) => s.status === "ok");

  return (
    <div className="space-y-2.5">
      <div className={`text-xs font-medium px-2.5 py-1 rounded-md inline-flex items-center gap-1.5 border ${
        allOk 
          ? "bg-eims-surface-subtle border-eims-border text-eims-text" 
          : "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400"
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${allOk ? "bg-eims-accent" : "bg-amber-500"}`} />
        {allOk ? "All Systems Operational" : "Degraded"}
      </div>
      <div className="space-y-1.5">
        {services.map((s) => (
          <div key={s.name} className="flex items-center justify-between text-xs py-0.5">
            <span className="text-eims-text-secondary">{s.name}</span>
            <div className="flex items-center gap-1.5">
              {s.status === "loading" && <Loader2 className="w-3.5 h-3.5 text-eims-text-muted animate-spin" />}
              {s.status === "ok" && (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-eims-accent" />
                  <span className="text-eims-text-secondary font-medium">Online</span>
                </>
              )}
              {s.status === "error" && (
                <>
                  <XCircle className="w-3.5 h-3.5 text-red-400" />
                  <span className="text-red-400 font-medium">Offline</span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
