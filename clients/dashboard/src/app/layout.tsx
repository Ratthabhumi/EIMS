import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Bell, User, Home, Grid, FileText, Settings, Shield, Compass, BookOpen, Star, BarChart3, Terminal, Activity, Database, HardDrive, Play, MonitorCheck, ScanText, Usb } from "lucide-react";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";
import { NotificationBell } from "@/components/NotificationBell";
import { SidebarNav } from "@/components/SidebarNav";
import { GlobalSearchDialog } from "@/components/GlobalSearchDialog";
import { Toaster } from "react-hot-toast";

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
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem enableColorScheme={false}>
          <Toaster position="top-right" toastOptions={{
            style: {
              background: 'var(--color-eims-surface)',
              color: 'var(--color-eims-text)',
              border: '1px solid var(--color-eims-border)'
            }
          }} />
          {/* Left Sidebar */}
        <aside className="w-64 bg-eims-surface border-r border-eims-border flex flex-col transition-all duration-200 shrink-0">
          <div className="h-16 flex items-center px-6 border-b border-eims-border">
            <div className="font-bold text-lg tracking-tight text-eims-text flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-sm bg-eims-accent"></span>
              EIMS Portal
            </div>
          </div>
          
          <SidebarNav />
        </aside>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 bg-eims-bg">
          {/* Top Header */}
          <header className="h-16 bg-eims-surface border-b border-eims-border flex items-center justify-between px-8 shrink-0">
            {/* Search Bar (Command Palette Hint) */}
            <GlobalSearchDialog />

            {/* Right Actions */}
            <div className="flex items-center gap-4">
              <ThemeToggle />
              <NotificationBell />
              <div className="h-6 w-px bg-eims-border"></div>
              <button className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                <div className="w-8 h-8 rounded-full bg-eims-surface-subtle border border-eims-border flex items-center justify-center">
                  <User className="w-4 h-4 text-eims-text-secondary" />
                </div>
              </button>
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-y-auto p-8 no-scrollbar">
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
