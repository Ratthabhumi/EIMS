"use client";
import { useEffect, useRef, useState } from "react";

// Packaged handover adapter only: preserves backend secure authentication.
// Token stays in memory. Never adds a bearer token to another origin.
export function HandoverAuthGate({ children }: { children: React.ReactNode }) {
  const [signedIn, setSignedIn] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const restore = useRef<null | (() => void)>(null);
  useEffect(() => () => restore.current?.(), []);
  const login = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    const api = process.env.NEXT_PUBLIC_EIMS_API_URL || "http://127.0.0.1:18101";
    try {
      const response = await fetch(api + "/api/v1/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "admin", password }),
      });
      if (!response.ok) throw new Error("Sign-in failed. Check your local account file.");
      const body = await response.json();
      if (typeof body.access_token !== "string" || !body.access_token) throw new Error("No access token returned.");
      const token = body.access_token;
      const original = window.fetch;
      window.fetch = async (input, init) => {
        const url = new URL(input instanceof Request ? input.url : String(input), window.location.href);
        if (url.origin !== new URL(api).origin || !url.pathname.startsWith("/api/")) return original(input, init);
        const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
        headers.set("Authorization", "Bearer " + token);
        const result = await original(input, { ...init, headers });
        if (result.status === 401) { restore.current?.(); restore.current=null; setSignedIn(false); setError("Session expired. Sign in again."); }
        return result;
      };
      restore.current = () => { window.fetch = original; };
      setPassword(""); setSignedIn(true);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Sign-in failed."); }
    finally { setBusy(false); }
  };
  if (signedIn) return <>{children}</>;
  return <main className="flex min-h-screen w-full items-center justify-center p-8">
    <form onSubmit={login} className="max-w-md space-y-4">
      <h1 className="text-2xl font-bold">EIMS local handover</h1>
      <p>Sign in as admin with the generated password in your private LOCAL_ADMIN.txt file. SETUP shows its local location. This installation uses synthetic examples.</p>
      <label className="block" htmlFor="handover-password">Local administrator password</label>
      <input id="handover-password" className="w-full border p-3" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} />
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={busy} className="border p-3">{busy ? "Signing in..." : "Sign in"}</button>
    </form>
  </main>;
}
