"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Home, 
  Terminal, 
  Shield, 
  Star, 
  Play, 
  Usb, 
  ScanText, 
  BarChart3, 
  HardDrive, 
  Database, 
  Activity, 
  History,
  Settings 
} from "lucide-react";

interface SidebarNavProps {
  onNavigate?: () => void;
}

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const pathname = usePathname();

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
      {/* 1. Main Navigation */}
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">Main</div>
        <Link href="/" className={getLinkClasses("/")} onClick={handleClick}>
          <Home className={getIconClasses("/")} /> Home Portal
        </Link>
      </div>

      {/* 2. Intelligent Operations & AI */}
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">Operations & AI</div>
        <Link href="/analyzer" className={getLinkClasses("/analyzer")} onClick={handleClick}>
          <Terminal className={getIconClasses("/analyzer")} /> AI Log Analyzer
        </Link>
        <Link href="/observability" className={getLinkClasses("/observability")} onClick={handleClick}>
          <Shield className={getIconClasses("/observability")} /> Observability & Alerts
        </Link>
        <Link href="/evaluations/admin" className={getLinkClasses("/evaluations/admin")} onClick={handleClick}>
          <Star className={getIconClasses("/evaluations/admin")} /> Service Evaluations
        </Link>
        <Link href="/timeline" className={getLinkClasses("/timeline")} onClick={handleClick}>
          <History className={getIconClasses("/timeline")} /> Timeline
        </Link>
      </div>

      {/* 3. Client Agents */}
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">Client Agents</div>
        <Link href="/agents" className={getLinkClasses("/agents")} onClick={handleClick}>
          <Play className={getIconClasses("/agents")} /> Client Agents
        </Link>
        <Link href="/endpoints" className={getLinkClasses("/endpoints")} onClick={handleClick}>
          <Usb className={getIconClasses("/endpoints")} /> USB Auditor
        </Link>
        <Link href="/ocr-history" className={getLinkClasses("/ocr-history")} onClick={handleClick}>
          <ScanText className={getIconClasses("/ocr-history")} /> Sticker OCR
        </Link>
      </div>

      {/* 4. Infrastructure & Management */}
      <div className="space-y-1">
        <div className="text-[11px] font-semibold text-eims-text-muted uppercase tracking-wider px-3 mb-2">System & Infra</div>
        <a 
          href="http://localhost:3000" 
          target="_blank" 
          rel="noopener noreferrer" 
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <BarChart3 className="w-4 h-4 text-eims-text-secondary" /> Grafana Metrics
        </a>
        <a 
          href="http://localhost:9001" 
          target="_blank" 
          rel="noopener noreferrer" 
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <HardDrive className="w-4 h-4 text-eims-text-secondary" /> MinIO Console
        </a>
        <a 
          href="http://localhost:9090" 
          target="_blank" 
          rel="noopener noreferrer" 
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <Database className="w-4 h-4 text-eims-text-secondary" /> Prometheus DB
        </a>
        <a 
          href="http://localhost:8000/api/docs" 
          target="_blank" 
          rel="noopener noreferrer" 
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-eims-text-secondary hover:text-eims-text hover:bg-eims-surface-subtle transition-colors"
        >
          <Activity className="w-4 h-4 text-eims-text-secondary" /> Core API Docs
        </a>
        <Link href="/settings" className={getLinkClasses("/settings")} onClick={handleClick}>
          <Settings className={getIconClasses("/settings")} /> Settings
        </Link>
      </div>
    </nav>
  );
}
