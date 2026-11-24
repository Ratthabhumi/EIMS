import { NextResponse } from "next/server";
import { readProfileExpect } from "@/lib/infra-profile-expect";

/**
 * Read-only, credential-free probes for System & Infrastructure consoles.
 * Never returns secrets. Failures are independent (one DOWN does not force others).
 *
 * Optional Observability services use:
 * - NOT_ENABLED when the profile is not expected and the probe cannot connect
 * - UNAVAILABLE when the profile is expected but the probe fails
 * - HEALTHY / DEGRADED when the probe succeeds
 */

export type InfraStatus = "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | "UNKNOWN" | "NOT_ENABLED";

type ProbeResult = {
  status: InfraStatus;
  checkedUrl: string;
  detail?: string;
  enableHint?: string;
};

function trimSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

function publicUrl(name: string, fallback: string): string {
  return trimSlash((process.env[name] || "").trim() || fallback);
}

/** Server-only MinIO S3 API base (health lives on API port, not Console UI). */
function minioApiBase(): string {
  const endpoint = (process.env.EIMS_MINIO_ENDPOINT || process.env.NEXT_PUBLIC_EIMS_MINIO_API_URL || "localhost:9000").trim();
  if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) return trimSlash(endpoint);
  const secure = (process.env.EIMS_MINIO_SECURE || "").trim() === "true";
  return `${secure ? "https" : "http"}://${endpoint.replace(/^\/\//, "")}`;
}

function backendOrigin(): string {
  return publicUrl("EIMS_BACKEND_URL", publicUrl("NEXT_PUBLIC_EIMS_API_URL", "http://localhost:8000"));
}

function isUnreachable(message: string): boolean {
  return /abort|timeout|ECONNREFUSED|fetch failed|network|ENOTFOUND/i.test(message);
}

async function probe(
  url: string,
  opts: {
    accept?: (status: number, body: string) => InfraStatus;
    timeoutMs?: number;
    /** When set and probe cannot connect, map refused → NOT_ENABLED instead of UNAVAILABLE. */
    notEnabledWhenUnreachable?: boolean;
    enableHint?: string;
  } = {},
): Promise<ProbeResult> {
  const timeoutMs = opts.timeoutMs ?? 2500;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    });
    const body = await res.text().catch(() => "");
    const status = opts.accept
      ? opts.accept(res.status, body)
      : res.ok
        ? "HEALTHY"
        : res.status >= 500
          ? "UNAVAILABLE"
          : "DEGRADED";
    return { status, checkedUrl: url, detail: `HTTP ${res.status}` };
  } catch (err) {
    const message = err instanceof Error ? err.message : "request failed";
    if (opts.notEnabledWhenUnreachable && isUnreachable(message)) {
      return {
        status: "NOT_ENABLED",
        checkedUrl: url,
        detail: "optional profile not started",
        enableHint: opts.enableHint,
      };
    }
    const unavailable = isUnreachable(message);
    return {
      status: unavailable ? "UNAVAILABLE" : "UNKNOWN",
      checkedUrl: url,
      detail: message.slice(0, 160),
      enableHint: opts.enableHint,
    };
  } finally {
    clearTimeout(timer);
  }
}

export async function GET() {
  const expect = readProfileExpect();
  const grafanaBase = publicUrl("NEXT_PUBLIC_EIMS_GRAFANA_URL", "http://localhost:3000");
  const minioConsole = publicUrl("NEXT_PUBLIC_EIMS_MINIO_CONSOLE_URL", "http://localhost:9001");
  const prometheusBase = publicUrl("NEXT_PUBLIC_EIMS_PROMETHEUS_URL", "http://localhost:9090");
  const apiBase = backendOrigin();
  const docsOverride = (process.env.NEXT_PUBLIC_EIMS_API_DOCS_URL || "").trim();
  const apiDocs = docsOverride ? trimSlash(docsOverride) : `${apiBase}/api/docs`;

  const obsHint = "Run start_eims_observability.bat (Compose profile: observability)";

  const [grafana, minioApi, minioConsoleProbe, prometheus, apiHealth, apiReady] = await Promise.all([
    probe(`${grafanaBase}/api/health`, {
      notEnabledWhenUnreachable: !expect.observability,
      enableHint: obsHint,
      accept: (code, body) => {
        if (code !== 200) return "UNAVAILABLE";
        try {
          const j = JSON.parse(body) as { database?: string };
          if (j.database === "ok") return "HEALTHY";
          if (j.database) return "DEGRADED";
        } catch {
          return "DEGRADED";
        }
        return "DEGRADED";
      },
    }),
    probe(`${minioApiBase()}/minio/health/live`, {
      accept: (code) => (code === 200 ? "HEALTHY" : "UNAVAILABLE"),
    }),
    probe(minioConsole, {
      accept: (code, body) => {
        if (code >= 200 && code < 400 && /minio/i.test(body)) return "HEALTHY";
        if (code >= 200 && code < 500) return "DEGRADED";
        return "UNAVAILABLE";
      },
    }),
    probe(`${prometheusBase}/-/ready`, {
      notEnabledWhenUnreachable: !expect.observability,
      enableHint: obsHint,
      accept: (code, body) => {
        if (code === 200 && /ready/i.test(body)) return "HEALTHY";
        if (code === 200) return "DEGRADED";
        return "UNAVAILABLE";
      },
    }),
    probe(`${apiBase}/api/v1/health`, {
      accept: (code, body) => {
        if (code === 200) {
          try {
            const j = JSON.parse(body) as { status?: string };
            if ((j.status || "").toUpperCase() === "HEALTHY") return "HEALTHY";
            return "DEGRADED";
          } catch {
            return "DEGRADED";
          }
        }
        if (code === 503) {
          try {
            const j = JSON.parse(body) as { status?: string };
            if ((j.status || "").toUpperCase() === "DEGRADED") return "DEGRADED";
          } catch {
            /* fall through */
          }
          return "DEGRADED";
        }
        return "UNAVAILABLE";
      },
    }),
    probe(`${apiBase}/api/v1/ready`, {
      accept: (code, body) => {
        if (code === 200) {
          try {
            const j = JSON.parse(body) as { status?: string; database?: boolean };
            if (j.status === "ready" && j.database !== false) return "HEALTHY";
            return "DEGRADED";
          } catch {
            return "DEGRADED";
          }
        }
        if (code === 503) return "DEGRADED";
        return "UNAVAILABLE";
      },
    }),
  ]);

  return NextResponse.json(
    {
      observedAt: new Date().toISOString(),
      profiles: {
        expectObservability: expect.observability,
        expectPooler: expect.pooler,
      },
      destinations: {
        grafana: grafanaBase,
        minioConsole,
        prometheus: prometheusBase,
        apiDocs,
        settings: "/settings",
      },
      services: {
        grafana,
        minioApi,
        minioConsole: minioConsoleProbe,
        prometheus,
        coreApiHealth: apiHealth,
        coreApiReady: apiReady,
      },
    },
    {
      status: 200,
      headers: {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}
