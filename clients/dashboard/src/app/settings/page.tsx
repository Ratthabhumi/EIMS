"use client";

import React, { useState } from "react";
import { Settings, Shield, Server, Bell, Key, Database, RefreshCw, CheckCircle2, Sliders } from "lucide-react";
import toast from "react-hot-toast";

export default function SettingsPage() {
  const [geminiApiKey, setGeminiApiKey] = useState("");
  const [retentionDays, setRetentionDays] = useState("90");
  const [vectorThreshold, setVectorThreshold] = useState("0.75");
  const [autoVectorSync, setAutoVectorSync] = useState(true);
  const [emailAlerts, setEmailAlerts] = useState(false);
  const [darkTheme, setDarkTheme] = useState(true);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success("Settings saved successfully!");
  };

  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-eims-text flex items-center gap-2.5">
          <Settings className="w-7 h-7 text-eims-info dark:text-sky-400" />
          System Settings & Preferences
        </h1>
        <p className="text-eims-text-secondary text-sm mt-1">
          Configure AI Models, Vector RAG retention, OCR endpoints, and notifications.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* 1. AI & Engine Configuration */}
        <div className="bg-eims-surface border border-eims-border rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-eims-border">
            <Key className="w-5 h-5 text-eims-info dark:text-sky-400" />
            <h2 className="text-base font-semibold text-eims-text">AI & Analysis Engine</h2>
          </div>

          <div className="grid grid-cols-1 gap-4">
            <div>
              <label className="block text-xs font-medium text-eims-text uppercase tracking-wider mb-1.5">
                Google Gemini API Key (Optional)
              </label>
              <input
                type="password"
                value={geminiApiKey}
                onChange={(e) => setGeminiApiKey(e.target.value)}
                placeholder="AIzaSy... (Leave empty to use 100% Free Local Vector DB)"
                className="w-full bg-eims-bg border border-eims-border rounded-lg px-4 py-2 text-sm text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-info transition-colors font-mono"
              />
              <p className="text-[11px] text-eims-text-secondary mt-1">
                If omitted, the system runs 100% offline using <strong>FastEmbed (384-dim)</strong> and Curated Diagnostic Base.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2">
              <div>
                <p className="text-sm font-medium text-eims-text">Auto-Sync Vector Knowledge Base</p>
                <p className="text-xs text-eims-text-secondary">Automatically generate embeddings and store verified log solutions.</p>
              </div>
              <input
                type="checkbox"
                checked={autoVectorSync}
                onChange={(e) => setAutoVectorSync(e.target.checked)}
                className="w-4 h-4 rounded text-sky-500 focus:ring-sky-400 bg-eims-bg border-eims-border cursor-pointer"
              />
            </div>
          </div>
        </div>

        {/* 2. Vector DB & Data Retention */}
        <div className="bg-eims-surface border border-eims-border rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-eims-border">
            <Database className="w-5 h-5 text-teal-400" />
            <h2 className="text-base font-semibold text-eims-text">Vector RAG & Storage</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-eims-text uppercase tracking-wider mb-1.5">
                Log History Retention (Days)
              </label>
              <select
                value={retentionDays}
                onChange={(e) => setRetentionDays(e.target.value)}
                className="w-full bg-eims-bg border border-eims-border rounded-lg px-3 py-2 text-sm text-eims-text focus:outline-none focus:border-eims-info transition-colors cursor-pointer"
              >
                <option value="30">30 Days</option>
                <option value="90">90 Days (Recommended)</option>
                <option value="180">180 Days</option>
                <option value="365">1 Year</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-eims-text uppercase tracking-wider mb-1.5">
                Cosine Similarity Threshold
              </label>
              <input
                type="number"
                step="0.05"
                min="0.5"
                max="0.95"
                value={vectorThreshold}
                onChange={(e) => setVectorThreshold(e.target.value)}
                className="w-full bg-eims-bg border border-eims-border rounded-lg px-4 py-2 text-sm text-eims-text focus:outline-none focus:border-eims-info transition-colors font-mono"
              />
            </div>
          </div>
        </div>

        {/* 3. Observability & Security Alerts */}
        <div className="bg-eims-surface border border-eims-border rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-eims-border">
            <Shield className="w-5 h-5 text-rose-400" />
            <h2 className="text-base font-semibold text-eims-text">Security & Alerting</h2>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-eims-text">Instant WebSocket Threat Notifications</p>
              <p className="text-xs text-eims-text-secondary">Push live alerts to the top header bell on Critical Event IDs (4625, 41, 1116).</p>
            </div>
            <span className="text-xs font-semibold text-teal-400 bg-teal-500/10 px-2.5 py-1 rounded border border-teal-500/20">
              Active
            </span>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex justify-end gap-3 pt-4">
          <button
            type="submit"
            className="bg-eims-info/20 hover:bg-eims-info/30 border border-eims-info/30 text-eims-info dark:text-sky-400 font-medium px-6 py-2.5 rounded-lg text-sm transition-all flex items-center gap-2 shadow-sm cursor-pointer"
          >
            <CheckCircle2 size={16} /> Save Configuration
          </button>
        </div>
      </form>
    </div>
  );
}
