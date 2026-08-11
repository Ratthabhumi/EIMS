"use client";

import { useState, useRef, useEffect } from "react";
import { Bell, ShieldAlert, CheckCircle2 } from "lucide-react";
import Link from "next/link";

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false);
  const [hasAlert, setHasAlert] = useState(false);
  const [missingComponents, setMissingComponents] = useState<string[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v1/health");
        const json = await res.json();
        
        const missing = [];
        if (json.components?.postgresql_pgbouncer_tier !== 'UP') missing.push('PostgreSQL');
        if (json.components?.redis_volatile_lru_tier !== 'UP') missing.push('Redis');
        if (json.components?.minio_object_storage_tier !== 'UP') missing.push('MinIO');
        
        if (json.status !== 'HEALTHY' || missing.length > 0) {
          setHasAlert(true);
          setMissingComponents(missing.length > 0 ? missing : ['Unknown Service']);
        } else {
          setHasAlert(false);
          setMissingComponents([]);
        }
      } catch (err) {
        setHasAlert(true);
        setMissingComponents(['API Gateway (Offline)']);
      }
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);

    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    
    return () => {
      clearInterval(interval);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="text-eims-text-secondary hover:text-eims-text transition-colors relative flex items-center justify-center p-1"
        title="Notifications"
      >
        <Bell className="w-5 h-5" />
        {hasAlert && (
          <span className="absolute top-1 right-1 block h-2 w-2 rounded-full bg-eims-error ring-2 ring-eims-surface animate-pulse"></span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-72 bg-eims-surface border border-eims-border rounded-md shadow-lg z-50 animate-fade-in">
          <div className="p-3 border-b border-eims-border">
            <h3 className="text-sm font-semibold text-eims-text">System Alerts</h3>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {hasAlert ? (
              <Link href="/observability" onClick={() => setIsOpen(false)} className="block p-3 hover:bg-eims-surface-subtle transition-colors border-b border-eims-border/50">
                <div className="flex gap-3 items-start">
                  <ShieldAlert className="w-4 h-4 text-eims-error shrink-0 mt-0.5" />
                  <div>
                    <p className="text-xs font-medium text-eims-text mb-1">SYSTEM DEGRADED</p>
                    <p className="text-[10px] text-eims-text-muted">
                      {missingComponents.join(', ')} connection lost.
                    </p>
                  </div>
                </div>
              </Link>
            ) : (
              <div className="p-5 flex flex-col items-center justify-center text-center gap-2">
                <CheckCircle2 className="w-6 h-6 text-eims-success opacity-80" />
                <p className="text-xs text-eims-text-muted">No active alerts. System is nominal.</p>
              </div>
            )}
          </div>
          <div className="p-2 border-t border-eims-border text-center bg-eims-surface-subtle/30 rounded-b-md">
            <Link 
              href="/observability" 
              onClick={() => setIsOpen(false)}
              className="text-xs font-medium text-eims-accent hover:underline block p-1"
            >
              Go to Observability Dashboard
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
