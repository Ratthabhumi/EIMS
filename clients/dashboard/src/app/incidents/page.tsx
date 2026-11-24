"use client";

/**
 * Compatibility shim: Incident Core lives inside Log Analyzer.
 * Preserve /incidents and /incidents?id=<uuid> by redirecting to /analyzer?incident=<uuid>.
 */

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function IncidentsRedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const id = (searchParams.get("id") || "").trim();
    const target = id ? `/analyzer?incident=${encodeURIComponent(id)}` : "/analyzer";
    router.replace(target);
  }, [router, searchParams]);

  return (
    <div className="p-8 text-sm text-eims-text-muted">
      Opening Incident Workspace inside Log Analyzer…
    </div>
  );
}

export default function IncidentsCompatPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-eims-text-muted">Redirecting…</div>}>
      <IncidentsRedirectInner />
    </Suspense>
  );
}
