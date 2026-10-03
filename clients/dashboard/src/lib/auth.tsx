"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";

interface UserProfile {
  username: string;
  role: string;
}

interface AuthContextType {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  login: (token: string, username: string, role?: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  isAuthenticated: false,
  login: () => {},
  logout: () => {},
});

const TOKEN_KEY = "eims_auth_token";
const USER_KEY = "eims_auth_user";

function parseJwt(token: string): { sub?: string; role?: string; exp?: number } | null {
  try {
    const base64Url = token.split(".")[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (storedToken) {
      const parsed = parseJwt(storedToken);
      if (parsed && parsed.exp && parsed.exp * 1000 < Date.now()) {
        // Expired token
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        setToken(null);
        setUser(null);
      } else {
        setToken(storedToken);
        if (storedUser) {
          try {
            setUser(JSON.parse(storedUser));
          } catch {
            setUser(parsed ? { username: parsed.sub || "admin", role: parsed.role || "user" } : null);
          }
        } else if (parsed) {
          setUser({ username: parsed.sub || "admin", role: parsed.role || "user" });
        }
      }
    }
  }, []);

  const login = (newToken: string, username: string, role: string = "user") => {
    const parsed = parseJwt(newToken);
    const resolvedRole = parsed?.role || role;
    const resolvedUser = { username, role: resolvedRole };

    localStorage.setItem(TOKEN_KEY, newToken);
    localStorage.setItem(USER_KEY, JSON.stringify(resolvedUser));
    setToken(newToken);
    setUser(resolvedUser);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated: !!token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
