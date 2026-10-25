import { createHash } from 'node:crypto';

/** Bounded per-process upstream protection; PostgreSQL is the shared authority. */
export class LoginGate {
  private accounts = new Map<string, { start: number; count: number }>();
  private global = { start: 0, count: 0 };
  constructor(private clock = Date.now) {}
  reserve(username: string): number {
    const now = this.clock(), window = 60000;
    for (const [key, value] of this.accounts) if (now - value.start >= window) this.accounts.delete(key);
    if (now - this.global.start >= window) this.global = { start: now, count: 0 };
    const key = createHash('sha256').update(username.trim().toLowerCase()).digest('hex');
    const account = this.accounts.get(key) || { start: now, count: 0 };
    if (this.global.count >= 60 || account.count >= 8 || this.accounts.size >= 1024 && !this.accounts.has(key))
      return Math.max(1, Math.ceil((window - Math.min(now-this.global.start, now-account.start))/1000));
    this.global.count++; account.count++; this.accounts.set(key, account);
    return 0;
  }
}
export const loginGate = new LoginGate();
