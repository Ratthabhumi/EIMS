"use client";

import { useState, useEffect } from "react";
import { Navbar } from "@/components/Navbar";
import { AdminPanel } from "@/components/AdminPanel";
import { AppSettings } from "@/lib/types";
import { DEFAULT_SETTINGS, loadSettings, applyTheme } from "@/lib/settings";
import { clearAuthToken, getAuthToken, getAuthUser } from "@/lib/api";
import { t } from "@/lib/i18n";
import { useRouter } from "next/navigation";

export default function AdminDashboard() {
  const [hydrated, setHydrated] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const router = useRouter();
  
  useEffect(() => {
    setSettings(loadSettings());
    const token = getAuthToken();
    const user = getAuthUser();
    
    if (!token || user?.role !== 'admin') {
      router.push("/");
    }
    setHydrated(true);
  }, [router]);

  useEffect(() => {
    if (!hydrated) return;
    applyTheme(settings.theme);
  }, [settings, hydrated]);

  const handleLogout = () => {
    clearAuthToken();
    router.push("/");
  };

  if (!hydrated) {
    return <div className="min-h-screen bg-[#f4f7f6] dark:bg-gray-900" />;
  }

  const lang = settings.language;

  return (
    <div className="min-h-screen bg-[#f4f7f6] dark:bg-gray-900">
      <Navbar
        settings={settings}
        onSettingsSave={setSettings}
        onLogout={handleLogout}
      />

      <main className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-semibold text-gray-800 dark:text-gray-100">
            {lang === 'th' ? "แผงควบคุมระบบ (Admin Dashboard)" : "Admin Dashboard"}
          </h1>
        </div>

        <AdminPanel settings={settings} />
      </main>
    </div>
  );
}
