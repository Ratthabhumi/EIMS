import { NextRequest, NextResponse } from 'next/server';
import { randomUUID } from 'node:crypto';

export const SESSION_COOKIE = 'eims_session';
const backend = () => process.env.EIMS_BACKEND_URL || process.env.NEXT_PUBLIC_EIMS_API_URL || 'http://localhost:8000';
export const origin = (req: NextRequest) => process.env.EIMS_DASHBOARD_ORIGIN || new URL(req.url).origin;
/** True when the browser Origin matches the Portal origin. Localhost and 127.0.0.1 are treated as the same host on matching protocol/port so Incident writes work whether the engineer opens either address. */
export const sameOrigin = (req: NextRequest) => {
  const incoming = req.headers.get('origin');
  if (!incoming) return false;
  const expected = origin(req);
  if (incoming === expected) return true;
  try {
    const a = new URL(incoming);
    const b = new URL(expected);
    const loopback = new Set(['localhost', '127.0.0.1']);
    return (
      a.protocol === b.protocol &&
      a.port === b.port &&
      loopback.has(a.hostname) &&
      loopback.has(b.hostname)
    );
  } catch {
    return false;
  }
};
export const cookieOptions = (req: NextRequest) => ({
  httpOnly: true, sameSite: 'strict' as const, path: '/',
  secure: !(process.env.EIMS_ALLOW_INSECURE_LOCAL_SESSION === '1'
    && ['localhost', '127.0.0.1'].includes(new URL(origin(req)).hostname)
    && new URL(origin(req)).protocol === 'http:'),
});
export const reply = (body: object, status = 200) => NextResponse.json(body, {
  status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
});
export const requestIdFor = (req: NextRequest) => {
  const incoming = req.headers.get('x-request-id') || '';
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(incoming)
    ? incoming : randomUUID();
};
export const withRequestId = (res: NextResponse, requestId: string) => {
  res.headers.set('X-Request-ID', requestId);
  return res;
};
export function clearSession(req: NextRequest, res: NextResponse) {
  res.cookies.set(SESSION_COOKIE, '', { ...cookieOptions(req), maxAge: 0 });
  return res;
}
/**
 * Structured, secret-free diagnostic for a BFF 5xx. Records only method, logical
 * route (no query string, no identifiers beyond the path), error class/code,
 * upstream status and duration. Never logs headers, cookies, tokens or bodies.
 */
export function logUpstreamFailure(req: NextRequest, startedAt: number, failure: { status?: number; error?: unknown }) {
  const err = failure.error as { name?: string; code?: string; cause?: { name?: string; code?: string } } | undefined;
  console.error(JSON.stringify({
    event: 'eims_bff_upstream_failure',
    method: req.method,
    path: new URL(req.url).pathname,
    upstreamStatus: failure.status,
    requestId: req.headers.get('x-request-id') || undefined,
    errorName: err?.name,
    errorCode: err?.code ?? err?.cause?.code,
    causeName: err?.cause?.name,
    clientAborted: req.signal?.aborted === true,
    durationMs: Math.round(performance.now() - startedAt),
  }));
}
/**
 * Every upstream call sends `Connection: close` so the BFF never reuses an idle
 * keep-alive socket that Uvicorn may already have timed out (surfaces as
 * ECONNRESET before any response). Applies to all methods: a reset on a reused
 * socket is equally possible for POST, which cannot be safely retried. No retry.
 */
export async function upstream(path: string, init: RequestInit = {}, requestId?: string) {
  const headers = new Headers(init.headers);
  if (requestId && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(requestId)) headers.set('X-Request-ID', requestId);
  headers.set('Connection', 'close');
  const startedAt = performance.now();
  const response = await fetch(`${backend().replace(/\/$/, '')}${path}`, {
    ...init, headers, cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(60000),
  });
  console.info(JSON.stringify({event:'eims_bff_upstream_response',requestId:requestId || undefined,
    method:init.method || 'GET',path:new URL(path,backend()).pathname,status:response.status,
    durationMs:Math.round(performance.now()-startedAt)}));
  return response;
}
export async function boundedBody(req: NextRequest, maximum = 40 * 1024 * 1024): Promise<ArrayBuffer> {
  const reader = req.body?.getReader();
  if (!reader) return new ArrayBuffer(0);
  const chunks: Uint8Array[] = []; let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maximum) { await reader.cancel(); throw new Error('BODY_TOO_LARGE'); }
    chunks.push(value);
  }
  const body = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return body.buffer;
}
