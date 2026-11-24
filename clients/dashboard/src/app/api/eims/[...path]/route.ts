import { NextRequest, NextResponse } from 'next/server';
import { boundedBody, clearSession, logUpstreamFailure, reply, requestIdFor, sameOrigin, SESSION_COOKIE, upstream, withRequestId } from '@/lib/session-proxy';

async function proxy(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const startedAt = performance.now();
  const requestId = requestIdFor(req);
  const { path } = await context.params;
  if (path.slice(0, 2).join('/') !== 'api/v1' || path.some(p => !p || /[\/\\?#%]|^\.{1,2}$/.test(p))
    || path[2] === 'auth' && path[3] === 'login') return withRequestId(reply({ detail: 'Unsupported API path' }, 404), requestId);
  if (!['GET', 'HEAD'].includes(req.method) && !sameOrigin(req)) return withRequestId(reply({ detail: 'Cross-origin request rejected' }, 403), requestId);
  try {
    const headers = new Headers();
    for (const name of ['content-type', 'accept']) { const value = req.headers.get(name); if (value) headers.set(name, value); }
    const token = req.cookies.get(SESSION_COOKIE)?.value;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const suffix = path.length === 3 && ['analyze', 'history', 'stats', 'knowledge'].includes(path[2]) ? '/' : '';
    const response = await upstream(`/${path.map(encodeURIComponent).join('/')}${suffix}${new URL(req.url).search}`, {
      method: req.method, headers, body: ['GET', 'HEAD'].includes(req.method) ? undefined : await boundedBody(req),
    }, requestId);
    const isDegradedHealth = req.method === 'GET' && path.length === 3 && path[2] === 'health' && response.status === 503;
    if (response.status >= 500 && !isDegradedHealth) {
      logUpstreamFailure(req, startedAt, { status: response.status });
      return withRequestId(reply({ detail: 'Analysis service unavailable' }, 502), requestId);
    }
    const total = response.headers.get('x-total-count');
    const result = new NextResponse(response.body, { status: response.status, headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      'X-Request-ID': response.headers.get('x-request-id') || requestId,
      // Pagination total for bounded list routes; a plain count, safe to pass through.
      ...(total && /^\d{1,9}$/.test(total) ? { 'X-Total-Count': total } : {}),
    } });
    return response.status === 401 ? clearSession(req, result) : result;
  } catch (error) {
    if (!(error instanceof Error && error.message === 'BODY_TOO_LARGE')) logUpstreamFailure(req, startedAt, { error });
    return withRequestId(reply({ detail: error instanceof Error && error.message === 'BODY_TOO_LARGE' ? 'Request too large' : 'Analysis service unavailable' },
      error instanceof Error && error.message === 'BODY_TOO_LARGE' ? 413 : 502), requestId);
  }
}
export { proxy as GET, proxy as POST, proxy as DELETE, proxy as PATCH, proxy as PUT };
