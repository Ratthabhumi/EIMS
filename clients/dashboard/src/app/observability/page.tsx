"use client";

import { useEffect, useState, useRef } from "react";
import { Shield, Activity, Search, Server, Database, HardDrive, Cpu, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface HealthData {
  system: string;
  version: string;
  status: string;
  components: {
    postgresql_pgbouncer_tier: string;
    redis_volatile_lru_tier: string;
    minio_object_storage_tier: string;
  }
}

const UptimeBar = ({ data }: { data: boolean[] }) => {
  return (
    <div className="flex items-center gap-[2px] mt-4 w-full h-5">
      {data.map((isUp, i) => (
        <div 
          key={i} 
          className={`flex-1 h-full rounded-sm opacity-80 hover:opacity-100 transition-opacity cursor-crosshair ${isUp ? 'bg-eims-success' : 'bg-eims-error'}`}
          title={isUp ? 'Operational' : 'Downtime'}
        />
      ))}
    </div>
  );
};

interface Alert {
  id: string;
  timestamp: string;
  message: string;
  severity: string;
  asset_id?: string;
  source_ip?: string;
}

export default function ObservabilityDashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [history, setHistory] = useState<{api: boolean[], pg: boolean[], redis: boolean[], minio: boolean[]}>(() => {
    const init = Array(40).fill(true);
    return { api: [...init], pg: [...init], redis: [...init], minio: [...init] };
  });
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchHealth = async () => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch("http://localhost:8000/api/v1/health", { signal: controller.signal });
      clearTimeout(timeoutId);
      const json = await res.json();
      setHealth(json);
      setHistory(prev => ({
        api: [...prev.api.slice(1), json.status === 'HEALTHY'],
        pg: [...prev.pg.slice(1), json.components?.postgresql_pgbouncer_tier === 'UP'],
        redis: [...prev.redis.slice(1), json.components?.redis_volatile_lru_tier === 'UP'],
        minio: [...prev.minio.slice(1), json.components?.minio_object_storage_tier === 'UP'],
      }));
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.warn("Health check timed out (backend degraded)");
      } else {
        console.warn("Failed to fetch health", err);
      }
      setHealth({
        system: "EIMS Core Gateway",
        version: "Unknown",
        status: "DEGRADED",
        components: {
          postgresql_pgbouncer_tier: "DOWN",
          redis_volatile_lru_tier: "DOWN",
          minio_object_storage_tier: "DOWN"
        }
      });
      setHistory(prev => ({
        api: [...prev.api.slice(1), false],
        pg: [...prev.pg.slice(1), false],
        redis: [...prev.redis.slice(1), false],
        minio: [...prev.minio.slice(1), false],
      }));
    }
  };

  useEffect(() => {
    fetchHealth();
    // Poll health every 15s
    const interval = setInterval(fetchHealth, 15000);
    
    // Connect to WebSocket
    const connectWs = () => {
      const ws = new WebSocket("ws://localhost:8000/api/v1/ws/dashboard");
      
      ws.onopen = () => console.log("Connected to Real-Time Alert Stream");
      
      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const newAlert: Alert = {
            id: Math.random().toString(36).substring(7),
            timestamp: new Date().toLocaleTimeString(),
            message: payload.event_type === "SECURITY_QUARANTINE_EXCEPTION" 
              ? `Brute force quarantine triggered for asset from IP ${payload.source_ip}` 
              : `System Alert: ${payload.event_type}`,
            severity: payload.severity || "Critical",
            asset_id: payload.asset_id,
            source_ip: payload.source_ip
          };
          setAlerts(prev => [newAlert, ...prev].slice(0, 10)); // Keep last 10
        } catch (e) {
          console.error("Failed to parse WS message", e);
        }
      };

      ws.onclose = () => {
        console.log("WS Disconnected. Reconnecting in 5s...");
        setTimeout(connectWs, 5000);
      };
      
      wsRef.current = ws;
    };

    connectWs();
    return () => {
      clearInterval(interval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  useEffect(() => {
    if (health && health.status !== 'HEALTHY') {
      const missing = [];
      if (health.components.postgresql_pgbouncer_tier !== 'UP') missing.push('PostgreSQL');
      if (health.components.redis_volatile_lru_tier !== 'UP') missing.push('Redis');
      if (health.components.minio_object_storage_tier !== 'UP') missing.push('MinIO');
      
      setAlerts(prev => {
        // Prevent spamming the same alert
        if (prev.length > 0 && prev[0].message.includes("SYSTEM DEGRADED")) return prev;
        
        const newAlert: Alert = {
          id: Math.random().toString(36).substring(7),
          timestamp: new Date().toLocaleTimeString(),
          message: `SYSTEM DEGRADED: ${missing.join(', ')} connection lost.`,
          severity: "Critical",
        };
        return [newAlert, ...prev].slice(0, 10);
      });
    }
  }, [health]);

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 h-full">
      <header className="flex items-center gap-4">
        <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-eims-text mb-1">System Health Monitor</h1>
          <p className="text-eims-text-secondary text-sm">Real-time internal diagnostics for EIMS Backend Infrastructure.</p>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        
        {/* Core Infrastructure Health */}
        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          
          <div className="surface-card p-6 flex flex-col justify-center">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Server className="w-5 h-5 text-eims-text-secondary" />
                <h3 className="font-medium text-eims-text">EIMS Core API</h3>
              </div>
              <span className={`px-2 py-1 text-xs font-bold uppercase rounded ${health?.status === 'HEALTHY' ? 'bg-eims-success/10 text-eims-success' : 'bg-eims-error/10 text-eims-error'}`}>
                {health?.status || "PENDING"}
              </span>
            </div>
            <p className="text-xs text-eims-text-muted">Port 8000 • FastAPI Gateway</p>
            <UptimeBar data={history.api} />
          </div>

          <div className="surface-card p-6 flex flex-col justify-center">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Database className="w-5 h-5 text-eims-text-secondary" />
                <h3 className="font-medium text-eims-text">PgBouncer Pool</h3>
              </div>
              <span className={`px-2 py-1 text-xs font-bold uppercase rounded ${health?.components.postgresql_pgbouncer_tier === 'UP' ? 'bg-eims-success/10 text-eims-success' : 'bg-eims-error/10 text-eims-error'}`}>
                {health?.components.postgresql_pgbouncer_tier || "PENDING"}
              </span>
            </div>
            <p className="text-xs text-eims-text-muted">Port 5432/6432 • PostgreSQL 16</p>
            <UptimeBar data={history.pg} />
          </div>

          <div className="surface-card p-6 flex flex-col justify-center">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Cpu className="w-5 h-5 text-eims-text-secondary" />
                <h3 className="font-medium text-eims-text">Redis Broker</h3>
              </div>
              <span className={`px-2 py-1 text-xs font-bold uppercase rounded ${health?.components.redis_volatile_lru_tier === 'UP' ? 'bg-eims-success/10 text-eims-success' : 'bg-eims-error/10 text-eims-error'}`}>
                {health?.components.redis_volatile_lru_tier || "PENDING"}
              </span>
            </div>
            <p className="text-xs text-eims-text-muted">Port 6379 • Volatile LRU Cache</p>
            <UptimeBar data={history.redis} />
          </div>

          <div className="surface-card p-6 flex flex-col justify-center">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <HardDrive className="w-5 h-5 text-eims-text-secondary" />
                <h3 className="font-medium text-eims-text">MinIO Storage</h3>
              </div>
              <span className={`px-2 py-1 text-xs font-bold uppercase rounded ${health?.components.minio_object_storage_tier === 'UP' ? 'bg-eims-success/10 text-eims-success' : 'bg-eims-error/10 text-eims-error'}`}>
                {health?.components.minio_object_storage_tier || "PENDING"}
              </span>
            </div>
            <p className="text-xs text-eims-text-muted">Port 9000/9001 • Object Storage</p>
            <UptimeBar data={history.minio} />
          </div>

        </div>

        {/* Live Event Feed */}
        <div className="surface-card p-6 flex flex-col h-full">
          <h2 className="text-base font-semibold text-eims-text mb-6 flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-eims-error opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-eims-error"></span>
            </span>
            Security Alert Stream
          </h2>
          
          <div className="flex-1 overflow-y-auto pr-2 space-y-3">
            {alerts.length === 0 ? (
              <div className="text-eims-text-muted text-sm text-center py-10 border border-dashed border-eims-border rounded-lg flex flex-col items-center justify-center gap-3 h-full">
                <Shield className="h-8 w-8 opacity-20" />
                No active alerts. System is nominal.
              </div>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="bg-eims-surface-subtle/50 border border-eims-border p-3 rounded-md animate-fade-in hover:bg-eims-surface-subtle transition-colors">
                  <div className="flex justify-between items-start mb-1.5">
                    <span className="text-eims-error text-[10px] font-bold uppercase tracking-wider bg-eims-error/10 px-1.5 py-0.5 rounded border border-eims-error/20">
                      {alert.severity}
                    </span>
                    <span className="text-eims-text-muted text-[10px]">{alert.timestamp}</span>
                  </div>
                  <p className="text-xs font-medium leading-relaxed text-eims-text">{alert.message}</p>
                  {alert.asset_id && (
                    <div className="mt-2 text-[10px] text-eims-text-muted font-mono truncate bg-eims-bg border border-eims-border p-1 rounded">
                      Target: {alert.asset_id}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
        
      </div>
    </div>
  );
}
