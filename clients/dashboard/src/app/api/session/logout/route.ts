import { NextRequest } from 'next/server';
import { clearSession, reply, requestIdFor, withRequestId } from '@/lib/session-proxy';

/** Clears any legacy session cookie. No application login remains. */
export async function POST(req: NextRequest) {
  const requestId = requestIdFor(req);
  const result = reply({ authenticated: false, application_login: false }, 200);
  return withRequestId(clearSession(req, result), requestId);
}
