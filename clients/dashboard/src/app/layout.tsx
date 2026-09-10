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
      <body className="flex h-screen overflow-hidden bg-eims-bg text-eims-text">
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
            <header className="h-16 bg-eims-surface border-b border-eims-border flex items-center justify-between px-8 shrink-0 lg:pl-0">
              {/* Search Bar (Command Palette Hint) */}
              <GlobalSearchDialog />

              {/* Right Actions */}
              <div className="flex items-center gap-4">
                <ThemeToggle />
                <NotificationBell />
                <div className="h-6 w-px bg-eims-border" />
                <button className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                  <div className="w-8 h-8 rounded-full bg-eims-surface-subtle border border-eims-border flex items-center justify-center">
                    <svg className="w-4 h-4 text-eims-text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
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
