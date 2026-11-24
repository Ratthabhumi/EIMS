import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";
import { NotificationBell } from "@/components/NotificationBell";
import { ResponsiveSidebar } from "@/components/ResponsiveSidebar";
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
      <head>
        {/* Apply saved/system theme before paint to avoid full-page color flicker (FOUC). */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('eims-theme')||'system';var d=t==='dark'||(t!=='light'&&window.matchMedia('(prefers-color-scheme: dark)').matches);var r=document.documentElement;r.classList.add(d?'dark':'light');r.classList.remove(d?'light':'dark');}catch(e){document.documentElement.classList.add('dark');}})();`,
          }}
        />
      </head>
      <body className="flex h-screen overflow-hidden bg-eims-bg text-eims-text" suppressHydrationWarning>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem enableColorScheme={false}>
          <Toaster position="top-right" toastOptions={{
            style: {
              background: 'var(--color-eims-surface)',
              color: 'var(--color-eims-text)',
              border: '1px solid var(--color-eims-border)'
            }
          }} />
          <ResponsiveSidebar />

          {/* Main Content Area */}
          <div className="flex-1 flex flex-col min-w-0 bg-eims-bg lg:pl-0">
            {/* Top Header */}
            <header className="h-16 bg-eims-surface border-b border-eims-border flex items-center justify-between gap-2 px-3 sm:px-6 lg:px-8 shrink-0 min-w-0">
              {/* Search Bar (Command Palette Hint) — shrinks on narrow viewports to avoid 499px overflow */}
              <div className="min-w-0 flex-1">
                <GlobalSearchDialog />
              </div>

              {/* Right Actions */}
              <div className="flex items-center gap-2 sm:gap-4 shrink-0">
                <ThemeToggle />
                <NotificationBell />
                <div className="hidden sm:block h-6 w-px bg-eims-border" />
                <button type="button" className="hidden sm:flex items-center gap-2 hover:opacity-80 transition-opacity" aria-label="Account">
                  <div className="w-8 h-8 rounded-full bg-eims-surface-subtle border border-eims-border flex items-center justify-center">
                    <svg className="w-4 h-4 text-eims-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                </button>
              </div>
            </header>

            {/* Page Content */}
            <main className="flex-1 overflow-y-auto p-4 sm:p-8 no-scrollbar min-w-0">
              <div className="max-w-5xl mx-auto h-full min-w-0">
                {children}
              </div>
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
