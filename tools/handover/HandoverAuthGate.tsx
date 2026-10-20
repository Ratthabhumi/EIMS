"use client";
import { useEffect, useRef, useState } from "react";

// Handover build only. JWT stays in memory; no permanent browser credentials.
export function HandoverAuthGate({ children }: { children: React.ReactNode }) {
  const [signedIn, setSignedIn] = useState(false);
  const [error, setError] = useState("");
  const started = useRef(false);
  const restore = useRef<null | (() => void)>(null);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const grant = new URLSearchParams(window.location.hash.slice(1)).get("eims-bootstrap");
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    if (!grant) { setError("Open EIMS with Start.bat on this PC."); return; }
    const api = process.env.NEXT_PUBLIC_EIMS_API_URL || "http://127.0.0.1:18101";
    const original = window.fetch;
    (async () => {
      try {
        const response = await original(api + "/api/v1/handover/session", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ proof: grant }), cache: "no-store",
        });
        if (!response.ok) throw new Error("Session unavailable");
        const body = await response.json();
        if (typeof body.access_token !== "string" || !body.access_token) throw new Error("Session unavailable");
        const token = body.access_token;
        window.fetch = async (input, init) => {
          const url = new URL(input instanceof Request ? input.url : String(input), window.location.href);
          if (url.origin !== new URL(api).origin || !url.pathname.startsWith("/api/")) return original(input, init);
          const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
          headers.set("Authorization", "Bearer " + token);
          const result = await original(input, { ...init, headers });
          if (result.status === 401) {
            restore.current?.(); restore.current = null; setSignedIn(false);
            setError("Session expired. Run Start.bat again.");
          }
          return result;
        };
        restore.current = () => { window.fetch = original; };
        setSignedIn(true);
      } catch { setError("Session could not open. Run Start.bat again."); }
    })();
  }, []);
  useEffect(() => () => restore.current?.(), []);
  if (signedIn) return <><div role="note" className="border-b px-4 py-2 text-sm">SYNTHETIC DEMO — fictional devices and findings for internal evaluation.</div>{children}</>;
  return <main className="flex min-h-screen items-center justify-center p-8">
    <div role="status" className="space-y-3"><h1 className="text-2xl font-bold">EIMS local handover</h1>
      <p>{error || "Opening your Windows-authorized session…"}</p></div>
  </main>;
}
