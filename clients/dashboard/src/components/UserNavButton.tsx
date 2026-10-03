"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { User, LogIn, LogOut, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";

export function UserNavButton() {
  const { user, isAuthenticated, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!isAuthenticated) {
    return (
      <Link
        href="/login"
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-eims-surface-subtle hover:bg-eims-surface border border-eims-border text-eims-text transition-colors"
      >
        <LogIn className="w-3.5 h-3.5 text-eims-accent" />
        <span>Sign in</span>
      </Link>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 p-1 rounded-full hover:opacity-80 transition-opacity focus:outline-none"
        title={user?.username || "Authenticated"}
      >
        <div className="w-8 h-8 rounded-full bg-eims-accent/15 border border-eims-accent/30 text-eims-accent flex items-center justify-center font-bold text-xs uppercase">
          {user?.username ? user.username.charAt(0) : "A"}
        </div>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-48 bg-eims-surface border border-eims-border rounded-xl shadow-lg py-1.5 z-50 animate-fade-in text-xs">
          <div className="px-3 py-2 border-b border-eims-border/60">
            <p className="font-semibold text-eims-text truncate">{user?.username || "admin"}</p>
            <p className="text-[10px] text-eims-text-muted uppercase tracking-wider flex items-center gap-1 mt-0.5">
              <ShieldCheck className="w-3 h-3 text-emerald-500" />
              Role: {user?.role || "admin"}
            </p>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="w-full flex items-center gap-2 px-3 py-2 text-left text-red-500 hover:bg-eims-surface-subtle transition-colors cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign out</span>
          </button>
        </div>
      )}
    </div>
  );
}
