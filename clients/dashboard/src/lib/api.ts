const API_BASE =
  process.env.NEXT_PUBLIC_EIMS_API_URL || "http://localhost:8000";

export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("eims_auth_token");
}

export function authHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...customHeaders };
  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchWithTimeout(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = 30000
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const token = getStoredToken();
  const headers = new Headers(init.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  try {
    const res = await fetch(apiUrl(path), {
      ...init,
      headers,
      signal: controller.signal,
    });

    if (res.status === 401 && typeof window !== "undefined") {
      // If we received a 401 and were authenticated, redirect to login
      if (token && window.location.pathname !== "/login") {
        localStorage.removeItem("eims_auth_token");
        localStorage.removeItem("eims_auth_user");
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
      }
    }

    return res;
  } finally {
    clearTimeout(timer);
  }
}

export function wsUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const wsBase = API_BASE.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");
  return `${wsBase}${normalized}`;
}
