"use client";

import { Usb, ScanText, Terminal, Download, ArrowLeft, Play } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function AgentsDashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string, type: 'success' | 'error' } | null>(null);

  const launchAgent = async (agentName: string) => {
    setLoading(agentName);
    setMessage(null);
    try {
      const res = await fetch("http://localhost:8000/api/v1/agents/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_name: agentName })
      });
      const data = await res.json();
      
      if (res.ok) {
        setMessage({ text: data.message, type: 'success' });
      } else {
        setMessage({ text: data.detail || "Failed to launch agent", type: 'error' });
      }
    } catch (err) {
      setMessage({ text: "Cannot connect to EIMS Backend", type: 'error' });
    } finally {
      setLoading(null);
      setTimeout(() => setMessage(null), 5000);
    }
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12">
      <header className="flex items-center gap-4">
        <Link href="/" className="p-2 rounded-full hover:bg-eims-surface-subtle text-eims-text-secondary hover:text-eims-text transition-colors shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-eims-text">Client Agents</h1>
          <p className="text-eims-text-secondary text-sm mt-1">Launch local desktop applications directly from the portal.</p>
        </div>
      </header>

      {message && (
        <div className={`p-4 rounded-md text-sm font-medium ${message.type === 'success' ? 'bg-eims-success/10 text-eims-success border border-eims-success/20' : 'bg-eims-error/10 text-eims-error border border-eims-error/20'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl">
        
        {/* USB Auditor */}
        <div 
          onClick={() => router.push('/endpoints')}
          className="surface-card p-6 flex flex-col gap-4 cursor-pointer hover:border-eims-accent/50 transition-colors border border-transparent"
        >
          <div className="flex items-start justify-between">
            <div className="w-12 h-12 rounded-xl bg-eims-surface-subtle flex items-center justify-center">
              <Usb className="w-6 h-6 text-eims-text-secondary" />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-eims-surface-subtle text-eims-text-secondary px-2 py-1 rounded">v1.2.0</span>
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-lg text-eims-text mb-2 hover:text-eims-accent transition-colors">USB Auditor Agent</h3>
            <p className="text-sm text-eims-text-secondary leading-relaxed">
              A lightweight Windows executable that extracts hardware specifications (CPU, RAM, Disks) and analyzes local Windows Event Logs for security anomalies.
            </p>
          </div>
          
          <button 
            onClick={(e) => {
              e.stopPropagation();
              launchAgent('usb_auditor');
              setTimeout(() => router.push('/endpoints'), 1000);
            }}
            disabled={loading === 'usb_auditor'}
            className="mt-4 flex items-center justify-center gap-2 w-full bg-eims-accent hover:opacity-90 text-white py-2.5 rounded-md font-medium text-sm transition-opacity disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            {loading === 'usb_auditor' ? 'Launching...' : 'Launch Agent'}
          </button>
        </div>

        {/* Sticker OCR */}
        <div 
          onClick={() => router.push('/ocr-history')}
          className="surface-card p-6 flex flex-col gap-4 cursor-pointer hover:border-eims-accent/50 transition-colors border border-transparent"
        >
          <div className="flex items-start justify-between">
            <div className="w-12 h-12 rounded-xl bg-eims-surface-subtle flex items-center justify-center">
              <ScanText className="w-6 h-6 text-eims-text-secondary" />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider bg-eims-surface-subtle text-eims-text-secondary px-2 py-1 rounded">v0.9.5-beta</span>
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-lg text-eims-text mb-2 hover:text-eims-accent transition-colors">Sticker OCR Pipeline</h3>
            <p className="text-sm text-eims-text-secondary leading-relaxed">
              Desktop interface for the IT department to scan and upload photos of hardware asset stickers directly into the MinIO Object Storage for AI processing.
            </p>
          </div>
          
          <button 
            onClick={(e) => {
              e.stopPropagation();
              launchAgent('sticker_ocr');
              setTimeout(() => router.push('/ocr-history'), 1000);
            }}
            disabled={loading === 'sticker_ocr'}
            className="mt-4 flex items-center justify-center gap-2 w-full bg-eims-accent hover:opacity-90 text-white py-2.5 rounded-md font-medium text-sm transition-opacity disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            {loading === 'sticker_ocr' ? 'Launching...' : 'Launch Agent'}
          </button>
        </div>

      </div>
    </div>
  );
}
