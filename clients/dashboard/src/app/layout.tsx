import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Search, Bell, User, Home, Grid, FileText, Settings, Shield, Compass, BookOpen, Star, BarChart3, Terminal, Activity, Database, HardDrive, Play, MonitorCheck } from "lucide-react";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EIMS Portal",
  description: "Enterprise Information Management System Portal",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="flex h-screen overflow-hidden bg-eims-bg text-eims-text">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          {/* Left Sidebar */}
        <aside className="w-64 bg-eims-surface border-r border-eims-border flex flex-col transition-all duration-200 shrink-0">
          <div className="h-16 flex items-center px-6 border-b border-eims-border">
            <div className="font-bold text-lg tracking-tight text-eims-text flex items-center gap-2">
              <div className="w-5 h-5 bg-eims-accent rounded-sm"></div>
              EIMS Portal
            </div>
          </div>
          
          <nav className="flex-1 overflow-y-auto py-6 px-4 space-y-1">
            <div className="text-xs font-medium text-eims-text-muted uppercase tracking-wider mb-3 px-2">Navigation</div>
            <Link href="/" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text transition-colors">
              <Home className="w-4 h-4 text-eims-text-secondary" /> Home
            </Link>

            <div className="mt-8 text-xs font-medium text-eims-text-muted uppercase tracking-wider mb-3 px-2 pt-4 border-t border-eims-border">Services</div>
            <a href="http://localhost:5173" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Terminal className="w-4 h-4 text-eims-text-secondary" /> AI Log Analyzer
            </a>
            <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <BarChart3 className="w-4 h-4 text-eims-text-secondary" /> Grafana Metrics
            </a>
            <a href="http://localhost:8000/api/docs" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Activity className="w-4 h-4 text-eims-text-secondary" /> Core API Docs
            </a>

            <div className="mt-8 text-xs font-medium text-eims-text-muted uppercase tracking-wider mb-3 px-2 pt-4 border-t border-eims-border">Client Tools</div>
            <Link href="/agents" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Play className="w-4 h-4 text-eims-text-secondary" /> Launch Agents
            </Link>
            <Link href="/endpoints" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <MonitorCheck className="w-4 h-4 text-eims-text-secondary" /> Endpoint Auditor
            </Link>

            <div className="mt-8 text-xs font-medium text-eims-text-muted uppercase tracking-wider mb-3 px-2 pt-4 border-t border-eims-border">Admin</div>
            <Link href="/evaluations/admin" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Star className="w-4 h-4 text-eims-text-secondary" /> Evaluations
            </Link>
            <Link href="/observability" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Shield className="w-4 h-4 text-eims-text-secondary" /> Observability
            </Link>

            <div className="mt-8 text-xs font-medium text-eims-text-muted uppercase tracking-wider mb-3 px-2 pt-4 border-t border-eims-border">Infrastructure</div>
            <a href="http://localhost:9001" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <HardDrive className="w-4 h-4 text-eims-text-secondary" /> MinIO Console
            </a>
            <a href="http://localhost:9090" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Database className="w-4 h-4 text-eims-text-secondary" /> Prometheus
            </a>
            
            <Link href="/settings" className="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium hover:bg-eims-surface-subtle text-eims-text-secondary transition-colors">
              <Settings className="w-4 h-4 text-eims-text-secondary" /> Settings
            </Link>
          </nav>
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-eims-bg">
          {/* Top Header */}
          <header className="h-16 bg-eims-surface border-b border-eims-border flex items-center justify-between px-8 shrink-0">
            {/* Search Bar (Command Palette Hint) */}
            <div className="flex items-center w-full max-w-md">
              <div className="relative w-full">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Search className="h-4 w-4 text-eims-text-muted" />
                </div>
                <input
                  type="text"
                  placeholder="Search the portal..."
                  className="block w-full pl-10 pr-12 py-2 border border-eims-border rounded-md leading-5 bg-eims-bg placeholder-eims-text-muted focus:outline-none focus:border-eims-accent focus:ring-1 focus:ring-eims-accent sm:text-sm transition-colors"
                />
                <div className="absolute inset-y-0 right-0 pr-2 flex items-center">
                  <kbd className="inline-flex items-center border border-eims-border rounded px-2 text-xs font-sans font-medium text-eims-text-muted bg-eims-surface-subtle">
                    ⌘K
                  </kbd>
                </div>
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-4">
              <ThemeToggle />
              <button className="text-eims-text-secondary hover:text-eims-text transition-colors relative">
                <Bell className="w-5 h-5" />
                <span className="absolute top-0 right-0 block h-2 w-2 rounded-full bg-eims-error ring-2 ring-eims-surface"></span>
              </button>
              <div className="h-6 w-px bg-eims-border"></div>
              <button className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <div className="w-8 h-8 rounded-full bg-eims-surface-subtle border border-eims-border flex items-center justify-center">
                  <User className="w-4 h-4 text-eims-text-secondary" />
                </div>
              </button>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-y-auto p-8">
            <div className="max-w-5xl mx-auto h-full">
              {children}
            </div>
          </main>
        </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
