'use client';

import React from 'react';
import { apiUrl } from '@/lib/api';

/**
 * Reviewer workflow for catalog candidates: queue -> draft -> submit -> human decision.
 * The browser never names a reviewer or an actor kind: the server derives both from the authenticated session.
 */
type QueueItem = {
  catalogId: string; class: string; title: string; contentHash: string; proposalStatus: string; lifecycle: string;
  missing: string[]; operationallyComplete: boolean; sources: number; revisions: number; draftAuthor?: string | null;
};
type GuidanceField = { status?: string; items?: string[]; source?: string; basis?: string; origin?: string };
type Detail = {
  status: string; stale: boolean; currentContentHash: string; draft?: Record<string, unknown> | null; draftAuthor?: string | null;
  class: string; catalogId: string; missing: string[]; revisions: number;
  eligibility?: { status: string; reasons: string[]; missing: string[] };
  view?: Record<string, unknown> & { evidenceAndSource?: { title?: string; url?: string; scope?: string }[]; versionScope?: string; whatHappened?: string };
  history: { type: string; actor: string; actorKind?: string; revision: number; at?: string; note?: string }[];
};

const FIELDS: { key: string; label: string; view: string }[] = [
  { key: 'required_permission', label: 'Required permission', view: 'requiredPermission' },
  { key: 'human_approval_required', label: 'Human approval requirement', view: 'humanApproval' },
  { key: 'rollback_steps', label: 'Rollback steps', view: 'rollback' },
  { key: 'verification_steps', label: 'Recovery verification', view: 'recoveryVerification' },
  { key: 'recovery_evidence', label: 'Recovery evidence', view: 'recoveryEvidence' },
  { key: 'recovery_success_criteria', label: 'Recovery success criteria', view: 'recoverySuccessCriteria' },
  { key: 'operational_impact', label: 'Operational impact', view: 'operationalImpact' },
  { key: 'destructive_risk', label: 'Destructive risk', view: 'destructiveRisk' },
];
type FormEntry = { enabled: boolean; state: 'stated' | 'unverified' | 'not_stated'; items: string; url: string; quote: string; retrieved: string; basis: string; reason: string };
const emptyEntry = (): FormEntry => ({ enabled: false, state: 'stated', items: '', url: '', quote: '', retrieved: new Date().toISOString().slice(0, 10), basis: '', reason: '' });
const SCOPE_BY_CLASS: Record<string, string> = { B: 'approved_as_diagnostic', C: 'approved_as_reference', D: 'approved_as_state_reference', E: 'approved_as_reference', F: 'approved_as_reference' };
const TARGETS = ['source_verified', 'validated', 'approved', 'rejected'] as const;

async function call(path: string, init?: RequestInit) {
  const response = await fetch(apiUrl('/api/v1/knowledge/governance' + path), { cache: 'no-store', ...init, headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) } });
  let data: any = null;
  try { data = await response.json(); } catch { data = null; }
  return { ok: response.ok, status: response.status, data };
}
const lines = (text: string) => text.split('\n').map((s) => s.trim()).filter(Boolean);
const problemText = (r: { status: number; data: any }) => {
  const d = r.data?.detail;
  if (typeof d === 'string') return `${r.status}: ${d}`;
  if (d?.message) return `${r.status} ${d.code || ''}: ${d.message}${d.missing ? ' — missing: ' + d.missing.join(', ') : ''}`;
  if (Array.isArray(d)) return `${r.status}: ${d.map((x: any) => (Array.isArray(x.loc) ? x.loc.slice(1).join('.') + ': ' : '') + x.msg).join('; ')}`;
  return `${r.status}: request failed`;
};

export default function ReviewerWorkflowPage() {
  const [canReview, setCanReview] = React.useState(false);
  const [user, setUser] = React.useState('');
  const [queue, setQueue] = React.useState<QueueItem[]>([]);
  const [filter, setFilter] = React.useState('');
  const [selected, setSelected] = React.useState('');
  const [detail, setDetail] = React.useState<Detail | null>(null);
  const [form, setForm] = React.useState<Record<string, FormEntry>>({});
  const [note, setNote] = React.useState('');
  const [preview, setPreview] = React.useState<any>(null);
  const [message, setMessage] = React.useState('');
  const [error, setError] = React.useState('');
  const [target, setTarget] = React.useState<(typeof TARGETS)[number]>('source_verified');
  const [rationale, setRationale] = React.useState('');
  const [evidenceRefs, setEvidenceRefs] = React.useState('');
  const [rv, setRv] = React.useState<Record<string, string>>({});
  const [busy, setBusy] = React.useState(false);

  const loadQueue = React.useCallback(async () => {
    setError('');
    let session: Response;
    try { session = await fetch(apiUrl('/api/v1/auth/session'), { cache: 'no-store' }); } catch { setCanReview(false); setQueue([]); setError('The EIMS backend is unreachable. Reviewer access cannot be determined; nothing is shown until it responds.'); return; }
    if (!session.ok) { setCanReview(false); setQueue([]); setError(`The EIMS backend could not confirm your session (HTTP ${session.status}). Reviewer access cannot be determined; try again when the service is healthy.`); return; }
    const info = await session.json();
    const reviewer = Boolean(info.capabilities?.knowledge_review);
    setCanReview(reviewer);
    setUser(info.username || info.user || '');
    const r = await call('/queue');
    if (!r.ok) { setError(problemText(r)); setQueue([]); return; }
    setQueue(r.data.items || []);
  }, []);
  React.useEffect(() => { const h = window.setTimeout(() => { void loadQueue(); }, 0); return () => window.clearTimeout(h); }, [loadQueue]);

  const open = async (catalogId: string) => {
    setSelected(catalogId); setMessage(''); setError(''); setPreview(null); setDetail(null);
    const r = await call('/proposals?catalog_id=' + encodeURIComponent(catalogId));
    if (!r.ok) { setError(problemText(r)); return; }
    const d: Detail = r.data;
    setDetail(d);
    const next: Record<string, FormEntry> = {};
    for (const f of FIELDS) {
      const e = (d.draft as any)?.[f.key];
      next[f.key] = e ? { ...emptyEntry(), enabled: true, state: e.state, items: (e.items || []).join('\n'), url: e.source?.url || '', quote: e.source?.quote || '', retrieved: e.source?.retrieved || emptyEntry().retrieved, basis: e.basis || '', reason: e.reason || '' } : emptyEntry();
    }
    setForm(next);
  };

  const content = () => {
    const out: Record<string, unknown> = {};
    for (const f of FIELDS) {
      const e = form[f.key];
      if (!e?.enabled) continue;
      if (e.state === 'stated') out[f.key] = { state: 'stated', items: lines(e.items), source: { url: e.url.trim(), quote: e.quote.trim(), retrieved: e.retrieved.trim() } };
      else if (e.state === 'unverified') out[f.key] = { state: 'unverified', items: lines(e.items), basis: e.basis.trim() };
      else out[f.key] = { state: 'not_stated', items: [], reason: e.reason.trim() };
    }
    return out;
  };
  const act = async (label: string, fn: () => Promise<{ ok: boolean; status: number; data: any }>) => {
    setBusy(true); setError(''); setMessage('');
    try {
      const r = await fn();
      if (!r.ok) { setError(problemText(r)); return null; }
      await loadQueue(); if (selected) await open(selected); setMessage(label);
      return r.data;
    } finally { setBusy(false); }
  };
  const base = () => ({ catalog_id: selected, base_hash: detail?.currentContentHash || '', content: content(), note });
  const doPreview = async () => { const r = await call('/proposals/preview', { method: 'POST', body: JSON.stringify({ catalog_id: selected, content: content() }) }); if (r.ok) setPreview(r.data); else setError(problemText(r)); };
  const decide = () => act(`Decision recorded: ${target}`, () => {
    const review: Record<string, unknown> = {};
    if (target === 'source_verified') Object.assign(review, { source_title: rv.source_title, source_url: rv.source_url, supporting_section: rv.supporting_section, claim_evidence: rv.claim_evidence, verified_at: rv.verified_at || new Date().toISOString(), vendor_product_scope: rv.vendor_product_scope });
    if (target === 'validated') Object.assign(review, { product_version_scope: rv.product_version_scope, applicability: rv.applicability, validation_basis: rv.validation_basis, verification_criteria: lines(rv.verification_criteria || '') });
    const body: Record<string, unknown> = { catalog_id: selected, target, content_hash: detail?.currentContentHash, rationale, review, evidence_refs: lines(evidenceRefs) };
    if (target === 'approved') body.approval_scope = SCOPE_BY_CLASS[detail?.class || ''];
    return call('/decisions', { method: 'POST', body: JSON.stringify(body) });
  });

  const shown = queue.filter((i) => !filter.trim() || (i.catalogId + ' ' + i.title).toLowerCase().includes(filter.trim().toLowerCase()));
  const input = 'w-full rounded border border-eims-border bg-eims-bg px-2 py-1 text-sm';
  return (
    <main className="mx-auto max-w-7xl p-6 space-y-4" data-testid="reviewer-workflow">
      <header>
        <h1 className="text-xl font-semibold text-eims-text">Knowledge reviewer workflow</h1>
        <p className="text-sm text-eims-text-secondary">Catalog candidates are shown with what they lack. Drafts are not active guidance until a human approves them. Your identity and role come from your session; they cannot be typed here.</p>
        <p className="text-xs text-eims-text-muted" data-testid="reviewer-capability">{canReview ? `Reviewer capability: yes${user ? ` (${user})` : ''}` : 'Reviewer capability: no. You can read the queue, records and history (open access); drafting and decisions require a reviewer session.'}</p>
      </header>
      {error && <div role="alert" className="rounded border border-red-500/40 bg-red-500/10 p-2 text-sm text-red-700 dark:text-red-400" data-testid="reviewer-error">{error}</div>}
      {message && <div className="rounded border border-emerald-500/40 bg-emerald-500/10 p-2 text-sm text-emerald-700 dark:text-emerald-400" data-testid="reviewer-message">{message}</div>}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section className="rounded-lg border border-eims-border bg-eims-surface p-3" aria-label="Reviewer queue">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-sm font-semibold text-eims-text">Queue ({shown.length})</h2>
            <input className={input} placeholder="Filter records" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter queue" />
          </div>
          <div className="max-h-[70vh] overflow-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-eims-text-muted"><th>Record</th><th className="px-2">Class</th><th className="px-2">Proposal</th><th className="px-2">Lacks</th></tr></thead>
              <tbody>
                {shown.map((i) => (
                  <tr key={i.catalogId} className={`cursor-pointer border-t border-eims-border ${selected === i.catalogId ? 'bg-eims-bg' : ''}`} onClick={() => void open(i.catalogId)} data-testid="queue-row">
                    <td className="py-1 pr-2 break-all"><button type="button" className="text-left underline" onClick={() => void open(i.catalogId)}>{i.catalogId}</button></td>
                    <td className="px-2">{i.class}</td><td className="px-2" data-testid="queue-status">{i.proposalStatus}</td>
                    <td className="px-2">{i.operationallyComplete ? 'complete' : i.missing.length + ' item(s)'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="rounded-lg border border-eims-border bg-eims-surface p-3 space-y-3" aria-label="Record review" data-testid="record-panel">
          {!detail && <p className="text-sm text-eims-text-muted">Select a record to review.</p>}
          {detail && (
            <>
              <div>
                <h2 className="text-sm font-semibold text-eims-text break-all">{detail.catalogId}</h2>
                <p className="text-xs text-eims-text-muted">Class {detail.class} · proposal <b data-testid="proposal-status">{detail.status}</b> · eligibility {detail.eligibility?.status} · hash <code>{detail.currentContentHash.slice(0, 12)}…</code></p>
                {detail.stale && <p className="text-xs text-amber-700 dark:text-amber-400" data-testid="stale-warning">STALE: the catalog record changed after this draft or approval was recorded. The old draft and any earlier approval no longer apply and the Analyzer ignores them. Re-save the draft to rebase it, then repeat source verification, validation and approval.</p>}
                <p className="text-sm text-eims-text-secondary mt-1">{detail.view?.whatHappened}</p>
                <p className="text-xs text-eims-text-muted">Version scope: {detail.view?.versionScope || 'not stated'}</p>
                <ul className="list-disc pl-5 text-xs">{(detail.view?.evidenceAndSource || []).map((s, k) => <li key={k}><a className="underline" href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a></li>)}</ul>
                <p className="text-xs mt-1" data-testid="missing-fields">Missing for operational use: {detail.missing.length ? detail.missing.join(', ') : 'nothing'}</p>
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-eims-text">Draft (operational fields)</h3>
                {FIELDS.map((f) => {
                  const cur = (detail.view as any)?.[f.view] as GuidanceField | undefined;
                  const e = form[f.key] || emptyEntry();
                  const set = (patch: Partial<FormEntry>) => setForm({ ...form, [f.key]: { ...e, ...patch } });
                  return (
                    <div key={f.key} className="rounded border border-eims-border p-2" data-testid={`field-${f.key}`}>
                      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={e.enabled} disabled={!canReview} onChange={(ev) => set({ enabled: ev.target.checked })} />{f.label}
                        <span className="text-[11px] text-eims-text-muted">catalog: {(cur?.status || 'not_stated').toUpperCase().replace('_', ' ')}</span></label>
                      {e.enabled && (
                        <div className="mt-2 grid gap-2">
                          <select className={input} value={e.state} onChange={(ev) => set({ state: ev.target.value as FormEntry['state'] })} aria-label={`${f.label} state`}>
                            <option value="stated">stated (official source required)</option><option value="unverified">unverified</option><option value="not_stated">not stated</option>
                          </select>
                          {e.state !== 'not_stated' && <textarea className={input} rows={2} placeholder="One item per line" value={e.items} onChange={(ev) => set({ items: ev.target.value })} aria-label={`${f.label} items`} />}
                          {e.state === 'stated' && (<>
                            <input className={input} placeholder="Official source URL (https)" value={e.url} onChange={(ev) => set({ url: ev.target.value })} aria-label={`${f.label} source url`} />
                            <textarea className={input} rows={2} placeholder="Verbatim quote from the source" value={e.quote} onChange={(ev) => set({ quote: ev.target.value })} aria-label={`${f.label} quote`} />
                            <input className={input} placeholder="Retrieved (YYYY-MM-DD)" value={e.retrieved} onChange={(ev) => set({ retrieved: ev.target.value })} aria-label={`${f.label} retrieved`} />
                          </>)}
                          {e.state === 'unverified' && <input className={input} placeholder="Basis: where this comes from" value={e.basis} onChange={(ev) => set({ basis: ev.target.value })} aria-label={`${f.label} basis`} />}
                          {e.state === 'not_stated' && <input className={input} placeholder="Reason: what was searched" value={e.reason} onChange={(ev) => set({ reason: ev.target.value })} aria-label={`${f.label} reason`} />}
                        </div>
                      )}
                    </div>
                  );
                })}
                <input className={input} placeholder="Note for the history" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Draft note" />
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="rounded border border-eims-border px-3 py-1 text-sm" onClick={() => void doPreview()} disabled={!canReview || busy} data-testid="btn-preview">Preview (no save)</button>
                  <button type="button" className="rounded border border-eims-border px-3 py-1 text-sm" onClick={() => void act('Draft saved', () => call('/proposals', { method: 'POST', body: JSON.stringify(base()) }))} disabled={!canReview || busy} data-testid="btn-save">Save draft</button>
                  <button type="button" className="rounded border border-eims-border px-3 py-1 text-sm" onClick={() => void act('Submitted for human review', () => call('/proposals/submit', { method: 'POST', body: JSON.stringify(base()) }))} disabled={!canReview || busy} data-testid="btn-submit">Submit for review</button>
                  <button type="button" className="rounded border border-eims-border px-3 py-1 text-sm" onClick={() => void act('Draft withdrawn', () => call('/proposals/withdraw', { method: 'POST', body: JSON.stringify(base()) }))} disabled={!canReview || busy} data-testid="btn-withdraw">Withdraw / request changes</button>
                </div>
                {preview && <div className="text-xs rounded border border-eims-border p-2" data-testid="preview-result">
                  <p>Validation: {preview.validationProblems.length ? preview.validationProblems.join('; ') : 'ok'}</p>
                  <p>Missing now: {preview.missingNow.join(', ') || 'nothing'} → with draft: {preview.missingWithDraft.join(', ') || 'nothing'}</p>
                  {preview.unverifiedFields.length > 0 && <p>Unverified (never counts as stated): {preview.unverifiedFields.join(', ')}</p>}
                </div>}
                <p className="text-xs text-eims-text-muted">History: {detail.history.length ? detail.history.map((h) => `${h.type} by ${h.actor}${h.actorKind ? ' (' + h.actorKind + ')' : ''}`).join(' → ') : 'no draft events'}</p>
              </div>
              <div className="space-y-2 border-t border-eims-border pt-2" data-testid="decision-panel">
                <h3 className="text-sm font-semibold text-eims-text">Human decision</h3>
                <p className="text-xs text-eims-text-muted">Recorded under your authenticated identity, bound to hash {detail.currentContentHash.slice(0, 12)}…. The author of a submitted draft cannot approve it.</p>
                <select className={input} value={target} onChange={(e) => setTarget(e.target.value as (typeof TARGETS)[number])} aria-label="Decision">
                  {TARGETS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                {target === 'source_verified' && ['source_title', 'source_url', 'supporting_section', 'claim_evidence', 'vendor_product_scope'].map((k) => <input key={k} className={input} placeholder={k} value={rv[k] || ''} onChange={(e) => setRv((cur) => ({ ...cur, [k]: e.target.value }))} aria-label={k} />)}
                {target === 'validated' && ['product_version_scope', 'applicability', 'validation_basis'].map((k) => <input key={k} className={input} placeholder={k} value={rv[k] || ''} onChange={(e) => setRv((cur) => ({ ...cur, [k]: e.target.value }))} aria-label={k} />)}
                {target === 'validated' && <textarea className={input} rows={2} placeholder="verification_criteria (one per line)" value={rv.verification_criteria || ''} onChange={(e) => setRv({ ...rv, verification_criteria: e.target.value })} aria-label="verification_criteria" />}
                {target === 'approved' && <p className="text-xs">Approval scope (from class): <b>{SCOPE_BY_CLASS[detail.class] || 'none — not approvable'}</b></p>}
                <textarea className={input} rows={2} placeholder="Rationale (at least 10 characters)" value={rationale} onChange={(e) => setRationale(e.target.value)} aria-label="Rationale" />
                <textarea className={input} rows={2} placeholder="Evidence references (https, one per line)" value={evidenceRefs} onChange={(e) => setEvidenceRefs(e.target.value)} aria-label="Evidence references" />
                <button type="button" className="rounded border border-eims-border px-3 py-1 text-sm" onClick={() => void decide()} disabled={!canReview || busy} data-testid="btn-decide">Record decision</button>
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
