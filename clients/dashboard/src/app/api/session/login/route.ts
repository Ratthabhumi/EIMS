import { NextRequest } from 'next/server';
import { reply, requestIdFor, withRequestId } from '@/lib/session-proxy';

/** Application login is not used. Keep the route as an explicit Gone response. */
export async function POST(req: NextRequest) {
  const requestId = requestIdFor(req);
  return withRequestId(
    reply(
      { detail: 'Application login is not used. EIMS Portal access does not require a user session.' },
      410,
    ),
    requestId,
  );
}
