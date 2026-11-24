import Link from "next/link";
import { infraConsoleUrls } from "@/lib/infra-consoles";
import { 
  Star, 
  Shield, 
  ArrowRight, 
  BarChart3, 
  Activity, 
  Terminal, 
  Database,
  Usb,
  Settings,
} from "lucide-react";

export default function HomeDashboard() {
  const infra = infraConsoleUrls();
  return (
    <div className="animate-fade-in flex flex-col gap-8 pb-12 max-w-4xl">
      {/* Hero Greeting */}
      <section className="pt-2">
        <h1 className="text-[30px] font-bold tracking-tight text-eims-text mb-1">Welcome to EIMS Portal</h1>
        <p className="text-eims-text-secondary text-sm">Select a module or service to continue.</p>
      </section>

      {/* 1. OPERATIONS (Matches Sidebar Group 1) */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-1.5 h-1.5 rounded-full bg-sky-500/70 dark:bg-sky-400/60"></div>
          <h2 className="text-xs font-semibold text-eims-text-muted uppercase tracking-wider">
            Operations
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link href="/analyzer" className="surface-card p-5 flex flex-col items-start gap-3 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-10 h-10 rounded-lg bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Terminal className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-base text-eims-text">Log Analyzer</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-xs text-eims-text-secondary mt-1">EVTX and raw log root-cause analysis with evidence-backed remediation.</p>
            </div>
          </Link>

          <Link href="/observability" className="surface-card p-5 flex flex-col items-start gap-3 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-10 h-10 rounded-lg bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Shield className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-base text-eims-text">Observability & Alerts</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-xs text-eims-text-secondary mt-1">Real-time telemetry feeds and quarantine alerts.</p>
            </div>
          </Link>

          <Link href="/evaluations/admin" className="surface-card p-5 flex flex-col items-start gap-3 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-10 h-10 rounded-lg bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Star className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-base text-eims-text">Service Evaluations</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-xs text-eims-text-secondary mt-1">Post-service customer feedback & QR code generation.</p>
            </div>
          </Link>
        </div>
      </section>

      {/* 2. ENDPOINT EVIDENCE — USB Auditor only; Client Agents / Sticker OCR cards removed to match primary nav (routes preserved). */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-600/70 dark:bg-emerald-400/60"></div>
          <h2 className="text-xs font-semibold text-eims-text-muted uppercase tracking-wider">
            Endpoint Evidence
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link href="/endpoints" className="surface-card p-5 flex flex-col items-start gap-3 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="w-10 h-10 rounded-lg bg-eims-surface-subtle flex items-center justify-center group-hover:bg-eims-accent/10 transition-colors">
              <Usb className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
            </div>
            <div className="w-full">
              <div className="flex justify-between items-center w-full">
                <h3 className="font-medium text-base text-eims-text">USB Auditor</h3>
                <ArrowRight className="w-4 h-4 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
              </div>
              <p className="text-xs text-eims-text-secondary mt-1">Import offline PC specs and hardware inventory.</p>
            </div>
          </Link>
        </div>
      </section>

      {/* 3. SYSTEM & INFRA (Matches Sidebar Group 3) */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-1.5 h-1.5 rounded-full bg-violet-600/70 dark:bg-violet-400/60"></div>
          <h2 className="text-xs font-semibold text-eims-text-muted uppercase tracking-wider">
            System & Infrastructure
          </h2>
        </div>
        {/* MinIO Console card hidden (OCR/object-store not in advisor walkthrough); compose + URL helpers unchanged. */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <a href={infra.grafana} target="_blank" rel="noopener noreferrer" className="surface-card p-4 flex flex-col items-start gap-2 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="flex justify-between items-center w-full">
              <BarChart3 className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
              <ArrowRight className="w-3.5 h-3.5 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
            </div>
            <div>
              <h3 className="font-medium text-sm text-eims-text">Grafana Metrics</h3>
              <p className="text-[11px] text-eims-text-secondary mt-0.5">Live telemetry.</p>
            </div>
          </a>

          <a href={infra.prometheus} target="_blank" rel="noopener noreferrer" className="surface-card p-4 flex flex-col items-start gap-2 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="flex justify-between items-center w-full">
              <Database className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
              <ArrowRight className="w-3.5 h-3.5 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
            </div>
            <div>
              <h3 className="font-medium text-sm text-eims-text">Prometheus DB</h3>
              <p className="text-[11px] text-eims-text-secondary mt-0.5">Time-series DB.</p>
            </div>
          </a>

          <a href={infra.apiDocs} target="_blank" rel="noopener noreferrer" className="surface-card p-4 flex flex-col items-start gap-2 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="flex justify-between items-center w-full">
              <Activity className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
              <ArrowRight className="w-3.5 h-3.5 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
            </div>
            <div>
              <h3 className="font-medium text-sm text-eims-text">Core API Docs</h3>
              <p className="text-[11px] text-eims-text-secondary mt-0.5">OpenAPI specs.</p>
            </div>
          </a>

          <Link href="/settings" className="surface-card p-4 flex flex-col items-start gap-2 hover:border-eims-accent transition-all group cursor-pointer hover:shadow-md">
            <div className="flex justify-between items-center w-full">
              <Settings className="w-5 h-5 text-eims-text-secondary group-hover:text-eims-accent" />
              <ArrowRight className="w-3.5 h-3.5 text-eims-text-muted group-hover:text-eims-accent transition-colors" />
            </div>
            <div>
              <h3 className="font-medium text-sm text-eims-text">Settings</h3>
              <p className="text-[11px] text-eims-text-secondary mt-0.5">Runtime health & readiness.</p>
            </div>
          </Link>
        </div>
      </section>
    </div>
  );
}
