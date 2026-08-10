"use client";

import { useEffect, useState, useRef } from "react";

interface Asset {
  asset_id: string;
  hostname: string;
  canonical_ip: string;
  lifecycle_state: string;
  current_compliance_score: number;
}

interface Alert {
  id: string;
  timestamp: string;
  message: string;
  severity: string;
  asset_id?: string;
  source_ip?: string;
}

export default function Dashboard() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const fetchAssets = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/assets?limit=100");
      if (res.ok) {
        const json = await res.json();
        setAssets(json.data || []);
      }
    } catch (err) {
      console.error("Failed to fetch assets", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
    
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
          
          // Refresh assets if quarantine happens to see the updated score
          if (payload.event_type === "SECURITY_QUARANTINE_EXCEPTION") {
            setTimeout(fetchAssets, 500); // Give DB time to commit
          }
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
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return (
    <main className="p-8 max-w-7xl mx-auto min-h-screen">
      <header className="mb-10 animate-fade-in">
        <h1 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
          EIMS Operational Dashboard
        </h1>
        <p className="text-slate-400 mt-2">Real-time Asset Registry & Security Observability</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Asset Table */}
        <div className="lg:col-span-2 glass-panel p-6 animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Registered Endpoints
          </h2>
          
          {loading ? (
            <div className="text-slate-400 py-10 text-center animate-pulse">Loading Asset Registry...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-400 text-sm uppercase tracking-wider">
                    <th className="pb-3 pr-4 font-medium">Hostname</th>
                    <th className="pb-3 pr-4 font-medium">IP Address</th>
                    <th className="pb-3 pr-4 font-medium">State</th>
                    <th className="pb-3 font-medium text-right">Compliance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {assets.map((asset) => (
                    <tr key={asset.asset_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-4 pr-4 font-medium">{asset.hostname}</td>
                      <td className="py-4 pr-4 text-slate-400 font-mono text-sm">{asset.canonical_ip}</td>
                      <td className="py-4 pr-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border
                          ${asset.lifecycle_state === 'Active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 
                            asset.lifecycle_state === 'Quarantined' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 
                            'bg-slate-500/10 text-slate-400 border-slate-500/20'}`}>
                          {asset.lifecycle_state}
                        </span>
                      </td>
                      <td className="py-4 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <span className={`font-semibold ${asset.current_compliance_score < 70 ? 'text-rose-400' : 'text-emerald-400'}`}>
                            {asset.current_compliance_score}
                          </span>
                          <div className="w-20 h-2 bg-slate-700 rounded-full overflow-hidden shadow-inner">
                            <div 
                              className={`h-full transition-all duration-1000 ${asset.current_compliance_score < 70 ? 'bg-rose-500' : 'bg-emerald-500'}`} 
                              style={{ width: `${asset.current_compliance_score}%` }}
                            ></div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {assets.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-slate-500 border border-dashed border-slate-700 rounded-lg">No assets registered yet. Ensure agents are communicating.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Live Event Feed */}
        <div className="glass-panel p-6 animate-fade-in flex flex-col" style={{ animationDelay: '0.2s', maxHeight: '600px' }}>
          <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
            </span>
            Security Alert Stream
          </h2>
          
          <div className="flex-1 overflow-y-auto pr-2 space-y-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
            {alerts.length === 0 ? (
              <div className="text-slate-500 text-center py-10 border border-dashed border-slate-700 rounded-lg flex flex-col items-center justify-center gap-3 h-full">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                No active alerts. System is nominal.
              </div>
            ) : (
              alerts.map((alert) => (
                <div key={alert.id} className="bg-slate-800/80 border border-rose-500/30 p-4 rounded-lg animate-fade-in shadow-[0_0_15px_rgba(244,63,94,0.1)] hover:bg-slate-800 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-rose-400 text-xs font-bold uppercase tracking-wider bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                      {alert.severity}
                    </span>
                    <span className="text-slate-400 text-xs">{alert.timestamp}</span>
                  </div>
                  <p className="text-sm font-medium leading-relaxed text-slate-200">{alert.message}</p>
                  {alert.asset_id && (
                    <div className="mt-3 text-[10px] text-slate-500 font-mono truncate bg-black/20 p-1.5 rounded">
                      Target: {alert.asset_id}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
        
      </div>
    </main>
  );
}
