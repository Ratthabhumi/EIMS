"use client";

import { useSyncExternalStore } from "react";
import { apiUrl } from "@/lib/api";

export interface HealthHistory {
  api: boolean[];
  pg: boolean[];
  redis: boolean[];
  minio: boolean[];
}

export interface HealthSnapshot {
  system: string;
  version: string;
  status: string;
  apiReachable: boolean;
  observedAt: string;
  components: {
    postgresql_pgbouncer_tier: string;
    redis_volatile_lru_tier: string;
    minio_object_storage_tier: string;
  };
  history: HealthHistory;
}

const initialHistory = (): HealthHistory => ({
  api: Array(40).fill(true), pg: Array(40).fill(true),
  redis: Array(40).fill(true), minio: Array(40).fill(true),
});
let history = initialHistory();
let snapshot: HealthSnapshot | null = null;

function publishHealth(data: Omit<HealthSnapshot, "apiReachable" | "history" | "observedAt">, apiReachable: boolean) {
  history = {
    api: [...history.api.slice(1), apiReachable && data.status === "HEALTHY"],
    pg: [...history.pg.slice(1), data.components.postgresql_pgbouncer_tier === "UP"],
    redis: [...history.redis.slice(1), data.components.redis_volatile_lru_tier === "UP"],
    minio: [...history.minio.slice(1), data.components.minio_object_storage_tier === "UP"],
  };
  snapshot = { ...data, apiReachable, observedAt: new Date().toLocaleTimeString(), history };
}
let request: Promise<void> | null = null;
let interval: ReturnType<typeof setInterval> | null = null;
const subscribers = new Set<() => void>();

async function refreshHealth(): Promise<void> {
  if (request) return request;
  request = (async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(apiUrl("/api/v1/health"), { signal: controller.signal });
      const data = await response.json();
      publishHealth(data, true);
    } catch {
      // API unreachable — do not imply each dependency was probed and found DOWN.
      publishHealth({
        system: "EIMS Core Gateway", version: "Unknown", status: "UNAVAILABLE",
        components: {
          postgresql_pgbouncer_tier: "UNAVAILABLE",
          redis_volatile_lru_tier: "UNAVAILABLE",
          minio_object_storage_tier: "UNAVAILABLE",
        },
      }, false);
    } finally {
      clearTimeout(timeout);
      request = null;
      subscribers.forEach((notify) => notify());
    }
  })();
  return request;
}

function subscribe(notify: () => void): () => void {
  subscribers.add(notify);
  if (interval === null) {
    void refreshHealth();
    interval = setInterval(() => void refreshHealth(), 15000);
  }
  return () => {
    subscribers.delete(notify);
    if (subscribers.size === 0 && interval !== null) {
      clearInterval(interval);
      interval = null;
    }
  };
}

export function useHealthStatus(): HealthSnapshot | null {
  return useSyncExternalStore(subscribe, () => snapshot, () => null);
}
