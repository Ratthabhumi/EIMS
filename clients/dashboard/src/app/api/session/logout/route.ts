import { NextRequest } from 'next/server';
import { clearSession, reply, sameOrigin, SESSION_COOKIE, upstream } from '@/lib/session-proxy';
export async function POST(req: NextRequest) {
  if (!sameOrigin(req)) return reply({ detail: 'Cross-origin request rejected' }, 403);
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (token) {
    try {
      const response = await upstream('/api/v1/auth/logout', { method:'POST', headers:{Authorization:`Bearer ${token}`} });
      if (!response.ok && response.status !== 401) return reply({ detail:'Logout unavailable; retry' },502);
    } catch { return reply({ detail:'Logout unavailable; retry' },502); }
  }
  return clearSession(req, reply({ authenticated: false }));
}
