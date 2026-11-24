"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { infraConsoleUrls, type InfraConsoleUrls } from "@/lib/infra-consoles";
import {
  Home,
  Terminal,
  Shield,
  Star,
  Usb,
  BarChart3,
  Database,
  Activity,
  History,
  Settings,
} from "lucide-react";

/** Stable SSR/first-paint defaults — avoids NEXT_PUBLIC_* server/client env skew. */
const INFRA_SSR_DEFAULTS: InfraConsoleUrls = {
  grafana: "http://localhost:3000",
  minioConsole: "http://localhost:9001",
  prometheus: "http://localhost:9090",
  apiDocs: "http://localhost:8000/api/docs",
};

interface SidebarNavProps {
  onNavigate?: () => void;
}

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const pathname = usePathname();
  const [infra, setInfra] = useState<InfraConsoleUrls>(INFRA_SSR_DEFAULTS);

  useEffect(() => {
    setInfra(infraConsoleUrls());
  }, []);

  const isActive = (path: string) => {
    if (path === "/" && pathname === "/") return true;
    if (path !== "/" && pathname?.startsWith(path)) return true;
    return false;
  };

  const getLinkClasses = (path: string) => {
    const active = isActive(path);
    return `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
      active
        ? "bg-eims-accent/15 text-eims-accent font-semibold"
        : "text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle"
    }`;
  };

  const getIconClasses = (path: string) => {
    const active = isActive(path);
    return `w-4 h-4 transition-colors ${
      active ? "text-eims-accent" : "text-eims-text-secondary"
    }`;
  };

  const handleClick = () => {
    onNavigate?.();
  };

  return (
    <nav className="flex-1 overflow-y-auto py-5 px-3 space-y-6" onClick={handleClick}>
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">Main</div>
        <Link prefetch={false} href="/" className={getLinkClasses("/")} onClick={handleClick}>
          <Home className={getIconClasses("/")} /> Home Portal
        </Link>
      </div>

      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">Operations</div>
        <Link prefetch={false} href="/analyzer" className={getLinkClasses("/analyzer")} onClick={handleClick}>
          <Terminal className={getIconClasses("/analyzer")} /> Log Analyzer
        </Link>
        <Link prefetch={false} href="/observability" className={getLinkClasses("/observability")} onClick={handleClick}>
          <Shield className={getIconClasses("/observability")} /> Observability & Alerts
        </Link>
        <Link prefetch={false} href="/evaluations/admin" className={getLinkClasses("/evaluations/admin")} onClick={handleClick}>
          <Star className={getIconClasses("/evaluations/admin")} /> Service Evaluations
        </Link>
        <Link prefetch={false} href="/timeline" className={getLinkClasses("/timeline")} onClick={handleClick}>
          <History className={getIconClasses("/timeline")} /> Timeline
        </Link>
      </div>

      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">Endpoint Evidence</div>
        <Link prefetch={false} href="/endpoints" className={getLinkClasses("/endpoints")} onClick={handleClick}>
          <Usb className={getIconClasses("/endpoints")} /> USB Auditor
        </Link>
      </div>

      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">System & Infra</div>
        <a
          href={infra.grafana}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <BarChart3 className="w-4 h-4 text-eims-text-secondary" /> Grafana Metrics
        </a>
        {/* MinIO Console hidden from nav (OCR/object-store demo not in advisor walkthrough); URL still in infraConsoleUrls. */}
        <a
          href={infra.prometheus}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <Database className="w-4 h-4 text-eims-text-secondary" /> Prometheus DB
        </a>
        <a
          href={infra.apiDocs}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <Activity className="w-4 h-4 text-eims-text-secondary" /> Core API Docs
        </a>
        <Link prefetch={false} href="/settings" className={getLinkClasses("/settings")} onClick={handleClick}>
          <Settings className={getIconClasses("/settings")} /> Settings
        </Link>
      </div>
    </nav>
  );
}
