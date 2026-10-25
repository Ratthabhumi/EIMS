import { NextRequest, NextResponse } from 'next/server';

export const SESSION_COOKIE = 'eims_session';
const backend = () => process.env.EIMS_BACKEND_URL || process.env.NEXT_PUBLIC_EIMS_API_URL || 'http://localhost:8000';
export const origin = (req: NextRequest) => process.env.EIMS_DASHBOARD_ORIGIN || new URL(req.url).origin;
export const sameOrigin = (req: NextRequest) => req.headers.get('origin') === origin(req);
export const cookieOptions = (req: NextRequest) => ({
  httpOnly: true, sameSite: 'strict' as const, path: '/',
  secure: !(process.env.EIMS_ALLOW_INSECURE_LOCAL_SESSION === '1'
    && ['localhost', '127.0.0.1'].includes(new URL(origin(req)).hostname)
    && new URL(origin(req)).protocol === 'http:'),
});
export const reply = (body: object, status = 200) => NextResponse.json(body, {
  status, headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' },
});
export function clearSession(req: NextRequest, res: NextResponse) {
  res.cookies.set(SESSION_COOKIE, '', { ...cookieOptions(req), maxAge: 0 });
  return res;
}
export async function upstream(path: string, init: RequestInit = {}) {
  return fetch(`${backend().replace(/\/$/, '')}${path}`, {
    ...init, cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(60000),
  });
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
