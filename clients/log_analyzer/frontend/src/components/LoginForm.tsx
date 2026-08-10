"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Lock, Eye, EyeOff } from "lucide-react";
import { AppLanguage, AppSettings } from "@/lib/types";
import { t } from "@/lib/i18n";
import { login } from "@/lib/api";

interface LoginFormProps {
  language: AppLanguage;
  settings: AppSettings;
  onLogin: () => void;
}

export function LoginForm({ language, settings, onLogin }: LoginFormProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const u = (document.getElementById("username") as HTMLInputElement).value;
    const p = (document.getElementById("password") as HTMLInputElement).value;
    setLoading(true);
    try {
      await login(settings, u, p);
      onLogin();
    } catch {
      alert(t(language, "invalidCredentials"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f4f7f6] dark:bg-gray-900 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 p-8 w-full max-w-md">
        <div className="flex flex-col items-center justify-center mb-8">
          <div className="bg-[#0078d4] p-3 rounded-full text-white mb-3 shadow-md">
            <Lock className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">{t(language, "loginTitle")}</h1>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">{t(language, "loginSubtitle")}</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t(language, "username")}</label>
            <Input id="username" type="text" placeholder="user" required className="w-full focus-visible:ring-[#0078d4]" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{t(language, "password")}</label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                required
                className="w-full focus-visible:ring-[#0078d4] pr-10"
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 focus:outline-none"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <Button type="submit" className="w-full bg-[#0078d4] hover:bg-[#006cbd] mt-2" disabled={loading}>
            {loading ? "Signing in..." : t(language, "signIn")}
          </Button>
        </form>
      </div>
    </div>
  );
}
