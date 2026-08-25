"use client";
import { useState, useEffect } from "react";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

type Status = "ok" | "error" | "loading";

interface ServiceStatus {
  name: string;
  status: Status;
}

export default function SystemStatusCard() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: "API Server", status: "loading" },
    { name: "Database", status: "loading" },
    { name: "Vector RAG", status: "loading" },
  ]);

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v1/health");
        if (res.ok || res.status === 503) {
          const data = await res.json();
          const c = data.components || {};
          setServices([
            { name: "API Server", status: "ok" },
            { name: "Database", status: c.postgresql_pgbouncer_tier === "UP" ? "ok" : "error" },
            { name: "Cache / Redis", status: c.redis_volatile_lru_tier === "UP" ? "ok" : "error" },
          ]);
        } else {
          setServices([
            { name: "API Server", status: "error" },
            { name: "Database", status: "error" },
            { name: "Cache / Redis", status: "error" },
          ]);
        }
      } catch {
        setServices([
          { name: "API Server", status: "error" },
          { name: "Database", status: "error" },
          { name: "Cache / Redis", status: "error" },
        ]);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

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
