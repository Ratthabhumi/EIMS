"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Shield, Key, Lock, User, ArrowRight } from "lucide-react";
import toast from "react-hot-toast";
import { apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectPath = searchParams.get("redirect") || "/";
  const { login } = useAuth();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast.error("Please enter both username and password");
      return;
    }

    setSubmitting(true);
    const toastId = toast.loading("Authenticating...");

    try {
      const res = await fetch(apiUrl("/api/v1/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Invalid credentials", { id: toastId });
        setSubmitting(false);
        return;
      }

      const data = await res.json();
      login(data.access_token, username.trim());
      toast.success("Welcome back!", { id: toastId });
      router.push(redirectPath);
    } catch (err) {
      console.error(err);
      toast.error("Network error while connecting to authentication service", { id: toastId });
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-eims-surface border border-eims-border rounded-2xl p-8 shadow-lg space-y-6">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-eims-surface-subtle border border-eims-border text-eims-accent mb-1">
          <Shield className="w-6 h-6 text-sky-400" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-eims-text">EIMS Portal Access</h1>
        <p className="text-sm text-eims-text-secondary">
          Enterprise Information Management System
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-eims-text-muted uppercase tracking-wider mb-1.5">
            Username
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-eims-text-muted">
              <User className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-eims-bg border border-eims-border rounded-xl text-sm text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-accent transition-colors"
              placeholder="admin"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-eims-text-muted uppercase tracking-wider mb-1.5">
            Password
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-eims-text-muted">
              <Lock className="w-4 h-4" />
            </div>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-eims-bg border border-eims-border rounded-xl text-sm text-eims-text placeholder-eims-text-muted focus:outline-none focus:border-eims-accent transition-colors"
              placeholder="••••••••••••"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-eims-accent hover:opacity-90 disabled:opacity-50 text-white rounded-xl text-sm font-semibold shadow-sm transition-all cursor-pointer mt-2"
        >
          {submitting ? "Signing in..." : "Sign in to Dashboard"}
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <div className="pt-4 border-t border-eims-border/60 text-center text-xs text-eims-text-muted">
        <p>Protected by EIMS Core Law 5 Security Engine</p>
        <p className="mt-0.5 text-[11px]">PBKDF2-SHA256 • JWT Bearer Token Authentication</p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-[75vh] items-center justify-center">
      <Suspense fallback={<div className="text-sm text-eims-text-muted">Loading authentication...</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
