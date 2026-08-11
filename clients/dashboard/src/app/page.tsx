import Link from "next/link";
import { Star, Shield, ArrowRight, BarChart3, Activity, Terminal, Database, HardDrive, Download, Usb, ScanText } from "lucide-react";

export default function HomeDashboard() {
  return (
    <div className="animate-fade-in flex flex-col gap-10 pb-12">
      {/* Hero Greeting */}
      <section className="pt-4">
        <h1 className="text-[32px] font-semibold tracking-tight text-eims-text mb-2">Welcome to EIMS Portal</h1>
        <p className="text-eims-text-secondary text-base">Select a module to continue.</p>
      </section>

      {/* Available Modules */}
      <section>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
          <Link href="/evaluations/admin" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Star className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">Service Evaluations</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Generate QR Codes and track customer satisfaction scores.</p>
            </div>
          </Link>
          
          <Link href="/observability" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Shield className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">Observability</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Monitor real-time security alerts and live telemetry data.</p>
            </div>
          </Link>

          <a href="http://localhost:5173" target="_blank" rel="noopener noreferrer" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Terminal className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">AI Log Analyzer</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Analyze Windows Event Logs using AI in a dedicated UI.</p>
            </div>
          </a>

          <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <BarChart3 className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">Grafana Metrics</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Deep infrastructure metrics and hardware telemetry.</p>
            </div>
          </a>

          <a href="http://localhost:8000/api/docs" target="_blank" rel="noopener noreferrer" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Activity className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">Core API Docs</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Interactive OpenAPI documentation for Asset Registry & Telemetry.</p>
            </div>
          </a>
        </div>
      </section>

      {/* Infrastructure & Core Services */}
      <section>
        <h2 className="text-xl font-semibold tracking-tight text-eims-text mb-4 mt-4">Infrastructure Services</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
          <a href="http://localhost:9001" target="_blank" rel="noopener noreferrer" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <HardDrive className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">MinIO Console</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Manage S3 Object Storage for OCR Manifests.</p>
            </div>
          </a>

          <a href="http://localhost:9090" target="_blank" rel="noopener noreferrer" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Database className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">Prometheus</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Raw metrics and time-series database dashboard.</p>
            </div>
          </a>
        </div>
      </section>

      {/* Client Agents & Tools */}
      <section>
        <h2 className="text-xl font-semibold tracking-tight text-eims-text mb-4 mt-4">Client Agents</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl">
          <Link href="/agents" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Usb className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">USB Auditor Agent</h3>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-eims-surface-subtle text-eims-text-secondary px-2 py-1 rounded">Desktop App</span>
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Windows executable script for extracting PC specs and logs.</p>
            </div>
          </Link>

          <Link href="/agents" className="surface-card p-6 flex flex-col items-start gap-4 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-12 h-12 rounded-full bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <ScanText className="w-6 h-6 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-lg text-eims-text">Sticker OCR Pipeline</h3>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-eims-surface-subtle text-eims-text-secondary px-2 py-1 rounded">Desktop App</span>
              </div>
              <p className="text-sm text-eims-text-secondary mt-1">Desktop tool for scanning asset stickers into MinIO storage.</p>
            </div>
          </Link>
        </div>
      </section>
    </div>
  );
}
