import { NextRequest, NextResponse } from 'next/server';
import { boundedBody, clearSession, reply, sameOrigin, SESSION_COOKIE, upstream } from '@/lib/session-proxy';

async function proxy(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.slice(0, 2).join('/') !== 'api/v1' || path.some(p => !p || /[\/\\?#%]|^\.{1,2}$/.test(p))
    || path[2] === 'auth' && path[3] === 'login') return reply({ detail: 'Unsupported API path' }, 404);
  if (!['GET', 'HEAD'].includes(req.method) && !sameOrigin(req)) return reply({ detail: 'Cross-origin request rejected' }, 403);
  try {
    const headers = new Headers();
    for (const name of ['content-type', 'accept']) { const value = req.headers.get(name); if (value) headers.set(name, value); }
    const token = req.cookies.get(SESSION_COOKIE)?.value;
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const suffix = path.length === 3 && ['analyze', 'history', 'stats'].includes(path[2]) ? '/' : '';
    const response = await upstream(`/${path.map(encodeURIComponent).join('/')}${suffix}${new URL(req.url).search}`, {
      method: req.method, headers, body: ['GET', 'HEAD'].includes(req.method) ? undefined : await boundedBody(req),
    });
    if (response.status >= 500) return reply({ detail: 'Analysis service unavailable' }, 502);
    const result = new NextResponse(response.body, { status: response.status, headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
      'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
    } });
    return response.status === 401 ? clearSession(req, result) : result;
  } catch (error) {
    return reply({ detail: error instanceof Error && error.message === 'BODY_TOO_LARGE' ? 'Request too large' : 'Analysis service unavailable' },
      error instanceof Error && error.message === 'BODY_TOO_LARGE' ? 413 : 502);
  }
}
export { proxy as GET, proxy as POST, proxy as DELETE, proxy as PATCH, proxy as PUT };
