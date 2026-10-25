import { NextRequest } from 'next/server';
import { boundedBody, cookieOptions, reply, sameOrigin, SESSION_COOKIE, upstream } from '@/lib/session-proxy';

export async function POST(req: NextRequest) {
  if (!sameOrigin(req)) return reply({ detail: 'Cross-origin request rejected' }, 403);
  try {
    const body = JSON.parse(new TextDecoder().decode(await boundedBody(req, 8192)));
    if (typeof body.username !== 'string' || typeof body.password !== 'string'
      || !body.username.trim() || !body.password || body.username.length > 256 || body.password.length > 4096)
      return reply({ detail: 'Enter username and password' }, 400);
    const response = await upstream('/api/v1/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: body.username, password: body.password }),
    });
    if (!response.ok) return reply({ detail: response.status === 401 ? 'Invalid username or password' : 'Login unavailable' }, response.status === 401 ? 401 : 502);
    const data = await response.json();
    const token = data.access_token;
    if (typeof token !== 'string' || token.length > 3800) return reply({ detail: 'Login unavailable' }, 502);
    // Expiry controls cookie lifetime only. Authorization remains backend-verified.
    const exp = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString()).exp;
    if (typeof exp !== 'number' || exp <= Date.now() / 1000) return reply({ detail: 'Login unavailable' }, 502);
    const result = reply({ authenticated: true });
    result.cookies.set(SESSION_COOKIE, token, { ...cookieOptions(req), maxAge: Math.min(86400, Math.floor(exp - Date.now() / 1000)) });
    return result;
  } catch (error) {
    if (error instanceof Error && error.message === 'BODY_TOO_LARGE') return reply({ detail: 'Request too large' }, 413);
    return reply({ detail: error instanceof SyntaxError ? 'Invalid login request' : 'Login unavailable' }, error instanceof SyntaxError ? 400 : 502);
  }
}
