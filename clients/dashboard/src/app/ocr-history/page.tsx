"use client";

import { useEffect, useState } from "react";
import { ScanText, Link as LinkIcon, Database, CheckCircle2, Clock, XCircle, Search, Download, ArrowLeft, ArrowDownAZ, ArrowUpZA } from "lucide-react";
import Link from "next/link";

interface OCRRecord {
  record_id: string;
  asset_id: string | null;
  minio_object_uri: string;
  extraction_status: string;
  parsed_raw_text: any;
}

export default function OCRHistoryDashboard() {
  const [records, setRecords] = useState<OCRRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  const fetchHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/assets/ocr-history");
      if (res.ok) {
        const json = await res.json();
        setRecords(json.data);
      }
    } catch (err) {
      console.error("Failed to fetch OCR history", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // Auto-refresh the history every 10 seconds so new scans appear automatically
    const interval = setInterval(fetchHistory, 10000);
    return () => clearInterval(interval);
  }, []);

  const StatusBadge = ({ status }: { status: string }) => {
    switch (status) {
      case "Completed":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-eims-success bg-eims-success/10 rounded-md border border-eims-success/20"><CheckCircle2 className="w-3.5 h-3.5" /> {status}</span>;
      case "Pending":
      case "Processing":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-eims-accent bg-eims-accent/10 rounded-md border border-eims-accent/20"><Clock className="w-3.5 h-3.5" /> {status}</span>;
      case "Failed":
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-eims-error bg-eims-error/10 rounded-md border border-eims-error/20"><XCircle className="w-3.5 h-3.5" /> {status}</span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-eims-text-muted bg-eims-surface-subtle rounded-md">{status}</span>;
    }
  };

  const getDisplayId = (record: OCRRecord) => {
    const did = record.parsed_raw_text?.extracted_did;
    const sn = record.parsed_raw_text?.extracted_sn;
    if (did && sn) {
      return `${did}(${sn})`;
    }
    return record.record_id;
  };

  const filteredRecords = records.filter(r => {
    const displayId = getDisplayId(r).toLowerCase();
    const term = search.toLowerCase();
    return r.record_id.toLowerCase().includes(term) || 
           r.minio_object_uri.toLowerCase().includes(term) ||
           displayId.includes(term);
  });

  const sortedRecords = [...filteredRecords].sort((a, b) => {
    const idA = getDisplayId(a).toLowerCase();
    const idB = getDisplayId(b).toLowerCase();
    return sortOrder === "asc" ? idA.localeCompare(idB) : idB.localeCompare(idA);
  });

  const getImageUrl = (uri: string) => {
    return `http://localhost:8000/api/v1/assets/ocr-history/image?uri=${encodeURIComponent(uri)}`;
  };

  const getDisplayFilename = (uri: string) => {
    const basename = uri.split('/').pop() || '';
    if (basename.length > 37 && basename.charAt(36) === '-') {
      return basename.substring(37);
    }
    return basename;
  };

  const exportToExcel = () => {
    if (sortedRecords.length === 0) return;
    
    const headers = ["Record ID", "Scanned Image Name", "Status", "Extracted Data", "Original URI"];
    const rows = sortedRecords.map(r => [
      getDisplayId(r),
      getDisplayFilename(r.minio_object_uri),
      r.extraction_status,
      r.parsed_raw_text ? JSON.stringify(r.parsed_raw_text).replace(/"/g, '""') : "",
      r.minio_object_uri
    ]);
    
    const csvContent = [
      headers.join(","),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(","))
    ].join("\n");
    
    const blob = new Blob(["\ufeff" + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `OCR_History_Report_${new Date().toISOString().slice(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 h-full">
      <header className="flex items-center gap-4">
        <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-eims-text">Sticker OCR History</h1>
          <p className="text-eims-text-secondary text-sm">Review processed sticker images and AI extraction results.</p>
        </div>
      </header>

      <div className="surface-card flex flex-col h-[calc(100vh-160px)]">
        {/* Toolbar */}
        <div className="p-4 border-b border-eims-border flex items-center justify-between shrink-0">
          <div className="relative w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-eims-text-muted" />
            <input
              type="text"
              placeholder="Search by ID or Object URI..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-eims-bg border border-eims-border rounded-md text-eims-text focus:outline-none focus:border-eims-accent focus:ring-1 focus:ring-eims-accent transition-colors"
            />
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm font-medium text-eims-text-muted">
              {filteredRecords.length} records found
            </div>
            <button 
              onClick={() => setSortOrder(prev => prev === "asc" ? "desc" : "asc")}
              className="flex items-center gap-2 px-3 py-1.5 bg-eims-surface-subtle hover:bg-eims-surface text-eims-text-secondary hover:text-eims-text rounded-md text-xs font-medium transition-all active:scale-95 focus:outline-none focus:ring-1 focus:ring-eims-text-secondary select-none"
              style={{ WebkitTapHighlightColor: 'transparent' }}
            >
              {sortOrder === "asc" ? <ArrowDownAZ className="w-3.5 h-3.5" /> : <ArrowUpZA className="w-3.5 h-3.5" />}
              Sort: {sortOrder === "asc" ? "A-Z" : "Z-A"}
            </button>
            <button 
              onClick={exportToExcel}
              disabled={filteredRecords.length === 0}
              className="flex items-center gap-2 px-3 py-1.5 bg-eims-accent hover:opacity-90 text-white rounded-md text-xs font-medium transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="w-3.5 h-3.5" />
              Export Excel (CSV)
            </button>
          </div>
        </div>

        {/* Data Table */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse min-w-[800px]">
            <thead className="sticky top-0 bg-eims-surface z-10">
              <tr>
                <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border w-1/4">Record ID</th>
                <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border">Scanned Image</th>
                <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border">Status</th>
                <th className="px-6 py-4 text-xs font-semibold text-eims-text-muted uppercase tracking-wider border-b border-eims-border">Extracted Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-eims-border bg-eims-surface">
              {loading ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-sm text-eims-text-muted">Loading history...</td>
                </tr>
              ) : filteredRecords.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-12 text-center text-sm text-eims-text-muted">
                    <div className="flex flex-col items-center gap-3 justify-center w-full">
                      <ScanText className="w-8 h-8 opacity-20 mx-auto" />
                      <span>No OCR history found.</span>
                    </div>
                  </td>
                </tr>
              ) : (
                sortedRecords.map((record) => (
                  <tr key={record.record_id} className="hover:bg-eims-surface-subtle/50 transition-colors">
                    <td className="px-6 py-4 text-sm text-eims-text font-mono truncate max-w-[200px]" title={`Internal ID: ${record.record_id}`}>
                      {getDisplayId(record)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div 
                          onClick={() => setSelectedImage(getImageUrl(record.minio_object_uri))} 
                          className="shrink-0 title='Click to view full image'"
                        >
                          <div className="w-10 h-10 rounded border border-eims-border overflow-hidden bg-eims-surface flex items-center justify-center hover:opacity-80 transition-opacity cursor-zoom-in shadow-sm">
                            <img 
                              src={getImageUrl(record.minio_object_uri)} 
                              alt="Sticker Scan" 
                              className="w-full h-full object-cover" 
                              onError={(e) => { e.currentTarget.style.display = 'none' }} 
                            />
                          </div>
                        </div>
                        <div className="flex flex-col">
                          <div className="flex items-center gap-1.5 text-xs text-eims-text-secondary mb-0.5">
                            <Database className="w-3 h-3 opacity-70" />
                            <span className="truncate max-w-[180px]" title={record.minio_object_uri}>{getDisplayFilename(record.minio_object_uri)}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={record.extraction_status} />
                    </td>
                    <td className="px-6 py-4">
                      {record.parsed_raw_text && Object.keys(record.parsed_raw_text).length > 0 ? (
                        <div className="text-xs bg-eims-bg border border-eims-border rounded p-2 text-eims-text-secondary font-mono break-all whitespace-pre-wrap max-w-sm max-h-32 overflow-y-auto">
                          {JSON.stringify(record.parsed_raw_text, null, 2)}
                        </div>
                      ) : (
                        <span className="text-xs text-eims-text-muted italic">No data</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedImage && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in"
          onClick={() => setSelectedImage(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh] bg-eims-surface rounded-lg border border-eims-border shadow-2xl p-2" onClick={e => e.stopPropagation()}>
            <button 
              onClick={() => setSelectedImage(null)}
              className="absolute -top-3 -right-3 w-8 h-8 bg-eims-surface border border-eims-border rounded-full flex items-center justify-center text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle shadow-md transition-colors"
            >
              <XCircle className="w-5 h-5" />
            </button>
            <img src={selectedImage} alt="Full Size Scan" className="max-w-full max-h-[calc(90vh-1rem)] object-contain rounded" />
          </div>
        </div>
      )}
    </div>
  );
}
