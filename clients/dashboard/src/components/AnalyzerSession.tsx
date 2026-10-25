'use client';
import { useEffect, useRef, useState } from 'react';
import { apiUrl } from '@/lib/api';

export default function AnalyzerSession() {
  const [session, setSession] = useState<{ username?: string; mode?: string } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const authenticated = useRef(false);
  async function refresh() {
    try {
      const response = await fetch(apiUrl('/api/v1/auth/session'), { cache: 'no-store' });
      if (response.status === 401 && authenticated.current) { window.location.reload(); return; }
      setSession(response.ok ? await response.json() : null);
      authenticated.current = response.ok;
      if (!response.ok && response.status !== 401) setError('Session service unavailable / ไม่สามารถตรวจ session ได้');
    } catch { setError('Session service unavailable / ไม่สามารถตรวจ session ได้'); }
  }
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, []);
  return <section className="bg-eims-surface border border-eims-border rounded-lg p-4 mb-4" aria-label="Analyzer session">
    {session ? <div className="flex flex-wrap items-center gap-3">
      <span>{session.mode === 'demo' ? 'Demo — shared identity / ใช้ตัวตนร่วมกัน' : `Signed in: ${session.username}`}</span>
      {session.mode !== 'demo' && <button className="underline" onClick={async () => {
        const r = await fetch('/api/session/logout', { method: 'POST' });
        if (r.ok) window.location.reload(); else setError('Logout failed');
      }}>Sign out / ออกจากระบบ</button>}
    </div> : <form className="flex flex-wrap gap-3 items-end" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      const data = new FormData(event.currentTarget);
      try {
        const r = await fetch('/api/session/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: data.get('username'), password: data.get('password') }) });
        if (r.ok) window.location.reload(); else setError('Sign-in failed / เข้าสู่ระบบไม่สำเร็จ');
      } catch { setError('Login unavailable'); } finally { setBusy(false); }
    }}>
      <label>Username / ชื่อผู้ใช้<input name="username" autoComplete="username" required className="block bg-eims-bg border border-eims-border rounded p-2" /></label>
      <label>Password / รหัสผ่าน<input name="password" type="password" autoComplete="current-password" required className="block bg-eims-bg border border-eims-border rounded p-2" /></label>
      <button disabled={busy} className="border border-eims-border rounded px-4 py-2">Sign in / เข้าสู่ระบบ</button>
      <p className="text-sm text-eims-text-secondary">Session expired or sign-in required / ต้องเข้าสู่ระบบหรือ session หมดอายุ</p>
    </form>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
