import { NextRequest } from 'next/server';
import { clearSession, reply, sameOrigin } from '@/lib/session-proxy';
export async function POST(req: NextRequest) {
  if (!sameOrigin(req)) return reply({ detail: 'Cross-origin request rejected' }, 403);
  return clearSession(req, reply({ authenticated: false }));
}
