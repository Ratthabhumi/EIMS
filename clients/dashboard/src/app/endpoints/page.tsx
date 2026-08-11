"use client";

import { useEffect, useState } from "react";
import { Upload, Cpu, Shield, Network, Server, HardDrive, Monitor, Clock, CheckCircle2, XCircle, Search, Download, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface Asset {
  asset_id: string;
  hostname: string;
  canonical_ip: string;
  cryptographic_fingerprint: string;
  lifecycle_state: string;
  current_compliance_score: number;
  created_at: string;
  updated_at: string;
  offline_report_data?: Record<string, any>;
}

export default function EndpointsDashboard() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const filteredAssets = assets.filter(asset => 
    asset.hostname.toLowerCase().includes(searchTerm.toLowerCase()) ||
    asset.canonical_ip.includes(searchTerm) ||
    asset.cryptographic_fingerprint.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const fetchAssets = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/assets?limit=100");
      if (res.ok) {
        const json = await res.json();
        const validAssets = (json.data || []).filter((a: Asset) => a.canonical_ip !== "0.0.0.0");
        setAssets(validAssets);
      }
    } catch (err) {
      console.error("Failed to fetch assets", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/v1/assets/import-report", {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        fetchAssets();
      } else {
        console.error("Upload failed");
      }
    } catch (err) {
      console.error("Failed to upload offline report", err);
    }
    e.target.value = '';
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const exportToExcel = () => {
    if (filteredAssets.length === 0) return;
    
    const headers = ["Hostname", "IP Address", "MAC Address", "State", "Compliance Score", "Created At", "Last Updated"];
    const rows = filteredAssets.map(a => [
      a.hostname,
      a.canonical_ip,
      a.cryptographic_fingerprint,
      a.lifecycle_state,
      String(a.current_compliance_score),
      a.created_at || "",
      a.updated_at || ""
    ]);
    
    const csvContent = [
      headers.join(","),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(","))
    ].join("\n");
    
    const blob = new Blob(["\ufeff" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `Endpoints_Report_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const StatusIcon = ({ status }: { status: any }) => {
    let displayStatus = status;
    let detailText = "";
    
    if (typeof status === 'object' && status !== null) {
      displayStatus = status.status || status.actual_state || status.protection_status || String(status);
      detailText = status.detail || "";
    }

    if (displayStatus === "PASS" || displayStatus === "Enabled" || displayStatus === "Running" || displayStatus === true || displayStatus === "Yes") {
      return <CheckCircle2 className="w-4 h-4 text-eims-success" title={detailText} />;
    }
    if (displayStatus === "FAIL" || displayStatus === "Disabled" || displayStatus === "Stopped" || displayStatus === false || displayStatus === "No") {
      return <XCircle className="w-4 h-4 text-eims-error" title={detailText} />;
    }
    if (displayStatus === "WARNING") {
      return <span className="text-orange-500 font-medium text-xs" title={detailText}>WARN</span>;
    }
    
    return <span className="text-eims-text-secondary truncate max-w-[100px]" title={detailText}>{String(displayStatus)}</span>;
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 h-full">
      <header className="flex items-center gap-4">
        <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-eims-text">USB Auditor</h1>
          <p className="text-eims-text-secondary text-sm">
            A lightweight Windows executable that extracts hardware specifications (CPU, RAM, Disks) and analyzes local Windows Event Logs for security anomalies.
          </p>
        </div>
      </header>

      <div className="surface-card flex flex-col h-[calc(100vh-180px)]">
        <div className="p-4 border-b border-eims-border flex items-center justify-between shrink-0">
          <div className="relative w-80">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-eims-text-muted" />
            <input 
              type="text"
              placeholder="Search by Hostname, IP, or Fingerprint..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-eims-bg border border-eims-border rounded-md text-eims-text focus:outline-none focus:border-eims-accent focus:ring-1 focus:ring-eims-accent transition-colors"
            />
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm font-medium text-eims-text-muted">
              {filteredAssets.length} endpoints found
            </div>
            <label className="cursor-pointer flex items-center gap-2 bg-eims-surface-subtle hover:bg-eims-border text-eims-text-secondary hover:text-eims-text px-3 py-1.5 rounded-md text-xs font-medium transition-colors border border-eims-border">
              <Upload className="w-3.5 h-3.5" />
              <span>Import Offline Report</span>
              <input type="file" accept=".json" className="hidden" onChange={handleFileUpload} />
            </label>
            <button 
              onClick={exportToExcel}
              disabled={filteredAssets.length === 0}
              className="flex items-center gap-2 px-3 py-1.5 bg-eims-accent hover:opacity-90 text-white rounded-md text-xs font-medium transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="w-3.5 h-3.5" />
              Export Excel (CSV)
            </button>
          </div>
        </div>
        
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="text-eims-text-muted py-10 text-center animate-pulse text-sm">Loading Asset Registry...</div>
          ) : (
            <table className="w-full text-left text-sm border-collapse min-w-[800px]">
              <thead className="sticky top-0 bg-eims-surface z-10">
                <tr>
                  <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border">Hostname</th>
                  <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border">IP Address</th>
                  <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border">State</th>
                  <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border text-right">Compliance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-eims-border bg-eims-surface">
                {filteredAssets.map((asset) => (
                  <tr 
                    key={asset.asset_id} 
                    className="hover:bg-eims-surface-subtle/50 transition-colors cursor-pointer"
                    onClick={() => setSelectedAsset(asset)}
                  >
                    <td className="px-6 py-4 text-eims-text font-medium">{asset.hostname}</td>
                    <td className="px-6 py-4 text-eims-text-secondary font-mono text-xs">{asset.canonical_ip}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border
                        ${asset.lifecycle_state === 'Active' || asset.lifecycle_state === 'Compliant' ? 'bg-eims-success/10 text-eims-success border-eims-success/20' : 
                          asset.lifecycle_state === 'Quarantined' || asset.lifecycle_state === 'NonCompliant' ? 'bg-eims-error/10 text-eims-error border-eims-error/20' : 
                          'bg-eims-surface-subtle text-eims-text-secondary border-eims-border'}`}>
                        {asset.lifecycle_state}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <span className={`font-semibold ${asset.current_compliance_score < 70 ? 'text-eims-error' : 'text-eims-success'}`}>
                          {asset.current_compliance_score}
                        </span>
                        <div className="w-16 h-1.5 bg-eims-border rounded-full overflow-hidden">
                          <div 
                            className={`h-full transition-all duration-1000 ${asset.current_compliance_score < 70 ? 'bg-eims-error' : 'bg-eims-success'}`} 
                            style={{ width: `${asset.current_compliance_score}%` }}
                          ></div>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredAssets.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-sm text-eims-text-muted">
                      <div className="flex flex-col items-center gap-3 justify-center w-full">
                        <Server className="w-8 h-8 opacity-20 mx-auto" />
                        <span>{assets.length === 0 ? "No assets registered yet. Ensure agents are communicating." : "No assets match your search."}</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Enhanced Asset Detail Modal */}
      {selectedAsset && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in overflow-y-auto">
          <div className="surface-card w-full max-w-6xl p-6 flex flex-col shadow-2xl my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-eims-border">
              <div>
                <h3 className="text-xl font-semibold text-eims-text flex items-center gap-2">
                  <Monitor className="w-5 h-5 text-eims-text-secondary" />
                  {selectedAsset.offline_report_data?.system?.computer_name || selectedAsset.hostname}
                </h3>
                <p className="text-eims-text-muted text-sm mt-1 flex items-center gap-4">
                  <span className="font-mono">{selectedAsset.canonical_ip}</span>
                  <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" /> Scanned: {selectedAsset.offline_report_data?.system?.scan_timestamp || "Unknown"}</span>
                </p>
              </div>
              <button 
                onClick={() => setSelectedAsset(null)}
                className="text-eims-text-muted hover:text-eims-text transition-colors p-2 hover:bg-eims-surface-subtle rounded-full"
              >
                ✕
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* Column 1: System */}
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-eims-text flex items-center gap-2 border-b border-eims-border pb-2">
                  <Cpu className="w-4 h-4 text-blue-400" />
                  System Specs
                </h4>
                <div className="space-y-3 text-sm">
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">OS Edition</div>
                    <div className="text-eims-text">{selectedAsset.offline_report_data?.system?.windows_edition || "N/A"}</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">Build Number</div>
                    <div className="text-eims-text font-mono">{selectedAsset.offline_report_data?.system?.build_number || "N/A"}</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">RAM & Disk</div>
                    <div className="text-eims-text">RAM: {selectedAsset.offline_report_data?.system?.ram_gb || "N/A"} GB / Disk: {selectedAsset.offline_report_data?.system?.disk_gb || "N/A"} GB</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">Timezone</div>
                    <div className="text-eims-text">{selectedAsset.offline_report_data?.setup_verify?.timezone?.timezone_id || "N/A"}</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">Username</div>
                    <div className="text-eims-text">{selectedAsset.offline_report_data?.system?.username || "N/A"}</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">Computer Name (Serial)</div>
                    <div className="text-eims-text truncate" title={selectedAsset.offline_report_data?.setup_verify?.computer_name_serial?.detail}>
                      {selectedAsset.offline_report_data?.setup_verify?.computer_name_serial?.status === "PASS" ? "Matched" : selectedAsset.offline_report_data?.setup_verify?.computer_name_serial?.computer_name || "N/A"}
                    </div>
                  </div>
                </div>
              </div>

              {/* Column 2: Network & Identity */}
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-eims-text flex items-center gap-2 border-b border-eims-border pb-2">
                  <Network className="w-4 h-4 text-purple-400" />
                  Network & Identity
                </h4>
                <div className="space-y-3 text-sm">
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">IP Address</div>
                    <div className="text-eims-text font-mono">{selectedAsset.offline_report_data?.system?.ip_address || selectedAsset.canonical_ip}</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">MAC Address</div>
                    <div className="text-eims-text font-mono text-xs">{selectedAsset.offline_report_data?.system?.mac_address || selectedAsset.cryptographic_fingerprint}</div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">WiFi Profiles</div>
                    <div className="flex items-center justify-between">
                      <span className="text-eims-text-secondary truncate max-w-[120px]" title={selectedAsset.offline_report_data?.setup_verify?.wifi_profiles?.detail}>
                        {selectedAsset.offline_report_data?.setup_verify?.wifi_profiles?.profile_count ?? "N/A"} Saved
                      </span>
                      <StatusIcon status={selectedAsset.offline_report_data?.setup_verify?.wifi_profiles || "Unknown"} />
                    </div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">SentinelOne</div>
                    <div className="flex items-center justify-between">
                      <span className="text-eims-text-secondary">Agent</span>
                      <StatusIcon status={selectedAsset.offline_report_data?.setup_verify?.sentinelone || "Unknown"} />
                    </div>
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">Setup Apps</div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-eims-text-secondary">New Outlook</span>
                      <StatusIcon status={selectedAsset.offline_report_data?.setup_verify?.new_outlook || "Unknown"} />
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-eims-text-secondary">Xbox</span>
                      <StatusIcon status={selectedAsset.offline_report_data?.setup_verify?.xbox || "Unknown"} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Column 3: Security & Registry */}
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-eims-text flex items-center gap-2 border-b border-eims-border pb-2">
                  <Shield className="w-4 h-4 text-eims-success" />
                  Security & Registry
                </h4>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Compliance Score</span>
                    <span className={`font-semibold ${selectedAsset.offline_report_data?.compliance?.score < 70 ? 'text-eims-error' : 'text-eims-success'}`}>
                      {selectedAsset.offline_report_data?.compliance?.score ?? selectedAsset.current_compliance_score} / 100
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Verdict</span>
                    <span className={`font-semibold ${selectedAsset.offline_report_data?.compliance?.verdict === "Non-Compliant" ? 'text-eims-error' : 'text-eims-success'}`}>
                      {selectedAsset.offline_report_data?.compliance?.verdict || "N/A"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Firewall</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.security?.firewall || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Windows Defender</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.security?.defender || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">BitLocker</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.security?.bitlocker || "Unknown"} />
                  </div>
                  <div>
                    <div className="text-eims-text-muted text-xs mb-1">BitLocker Key</div>
                    <div className="text-eims-text font-mono text-xs truncate" title={selectedAsset.offline_report_data?.security?.bitlocker?.recovery_key}>
                      {selectedAsset.offline_report_data?.security?.bitlocker?.recovery_key || "N/A"}
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-eims-border/50">
                    <span className="text-eims-text-secondary">UAC Enabled</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.registry?.UAC || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">RDP Disabled</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.registry?.RDP || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">SMBv1 Disabled</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.registry?.SMBv1 || "Unknown"} />
                  </div>
                </div>
              </div>

              {/* Column 4: Services */}
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-eims-text flex items-center gap-2 border-b border-eims-border pb-2">
                  <Server className="w-4 h-4 text-orange-400" />
                  Services & Updates
                </h4>
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Windows Update</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.security?.windows_update || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">WinDefend Svc</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.services?.WinDefend || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">BITS Svc</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.services?.BITS || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Windows Upd Svc</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.services?.wuauserv || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">Remote Registry</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.services?.RemoteRegistry || "Unknown"} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-eims-text-secondary">W32Time Svc</span>
                    <StatusIcon status={selectedAsset.offline_report_data?.services?.W32Time || "Unknown"} />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-4 border-t border-eims-border flex justify-end gap-3">
              <button 
                onClick={() => setSelectedAsset(null)}
                className="bg-eims-surface-subtle hover:bg-eims-border text-eims-text px-6 py-2 rounded-md text-sm font-medium transition-colors"
              >
                Close View
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
