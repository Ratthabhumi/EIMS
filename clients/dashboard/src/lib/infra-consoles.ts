/**
 * Public console destinations for System & Infrastructure menu items.
 * Defaults match docker-compose.yml local bindings. Override via NEXT_PUBLIC_*
 * URL env vars only — never put credentials in these values.
 */

function trimTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

function readPublicUrl(name: string, fallback: string): string {
  const raw = (process.env[name] || "").trim();
  return trimTrailingSlash(raw || fallback);
}

/** Backend origin used only to build the OpenAPI docs URL when docs env is unset. */
function backendOrigin(): string {
  return readPublicUrl("NEXT_PUBLIC_EIMS_API_URL", "http://localhost:8000");
}

export type InfraConsoleUrls = {
  grafana: string;
  minioConsole: string;
  prometheus: string;
  apiDocs: string;
};

/**
 * Browser-safe console URLs (no secrets). Defaults:
 * - Grafana :3000 (compose eims-grafana)
 * - MinIO Console :9001 (compose --console-address; S3 API remains :9000)
 * - Prometheus :9090
 * - Core API Docs: FastAPI /api/docs on the backend origin
 */
export function infraConsoleUrls(): InfraConsoleUrls {
  const docsOverride = (process.env.NEXT_PUBLIC_EIMS_API_DOCS_URL || "").trim();
  return {
    grafana: readPublicUrl("NEXT_PUBLIC_EIMS_GRAFANA_URL", "http://localhost:3000"),
    minioConsole: readPublicUrl("NEXT_PUBLIC_EIMS_MINIO_CONSOLE_URL", "http://localhost:9001"),
    prometheus: readPublicUrl("NEXT_PUBLIC_EIMS_PROMETHEUS_URL", "http://localhost:9090"),
    apiDocs: docsOverride
      ? trimTrailingSlash(docsOverride)
      : `${backendOrigin()}/api/docs`,
  };
}

/** Labels for System & Infrastructure in Home/Sidenav (MinIO Console UI-hidden for advisor demo). */
export const INFRA_MENU_LABELS = [
  "Grafana Metrics",
  "Prometheus DB",
  "Core API Docs",
  "Settings",
] as const;
