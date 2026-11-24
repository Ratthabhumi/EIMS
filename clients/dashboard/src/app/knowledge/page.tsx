'use client';

import React from 'react';
import { apiUrl } from '@/lib/api';

type SourceCandidate = {
  id: number; sourceKey: string; vendor: string; product: string; versionScope: string;
  domain: string; identity: string; title: string; url: string; applicability: string;
  prerequisites: string[]; evidence: string[]; limitations: string[]; nextChecks: string[];
  validation: string[]; rollback: string[]; riskLevel: string; evidenceStatus: string;
  reviewState: 'pending_domain_review' | 'verified_reference' | 'rejected' | 'revalidation_required' | 'withdrawn';
  catalogSchemaVersion: string; catalogueRecordHash: string; importedAt: string | null;
  reviewedBy: string | null; reviewedAt: string | null; reviewNote: string; updatedAt: string | null;
};

type Entry = {
  id: number; title: string; sourceFamily: string; diagnosticIdentity: string;
  resolutionStatus: string; rootCause: string; solutionSteps: string[];
  impact: string; prevention: string; productName: string | null; productVersion: string | null;
  environment: string | null; prerequisites: string[]; riskLevel: string;
  validationSteps: string[]; rollbackSteps: string[]; evidenceNotes: string[]; references: string[];
  status: string; sourceHistoryHash: string; proposedBy: string;
  reviewedBy: string | null; reviewedAt: string | null; reviewNote: string;
  lifecycleState: 'active' | 'revalidation_required' | 'superseded' | 'withdrawn';
  lifecycleReason: string; lifecycleUpdatedAt: string | null; supersededById: number | null;
};

async function json(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

export default function KnowledgePage() {
  const [entries, setEntries] = React.useState<Entry[]>([]);
  const [queue, setQueue] = React.useState<Entry[]>([]);
  const [lifecycleQueue, setLifecycleQueue] = React.useState<Entry[]>([]);
  const [sourceCandidates, setSourceCandidates] = React.useState<SourceCandidate[]>([]);
  const [sourceReviewNotes, setSourceReviewNotes] = React.useState<Record<number, string>>({});
  const [sourceBusyId, setSourceBusyId] = React.useState<number | null>(null);
  const [sourceEvents, setSourceEvents] = React.useState<Record<number, Array<Record<string, unknown>>>>({});
  const [lifecycleReasons, setLifecycleReasons] = React.useState<Record<number, string>>({});
  const [lifecycleNotes, setLifecycleNotes] = React.useState<Record<number, string>>({});
  const [replacementIds, setReplacementIds] = React.useState<Record<number, string>>({});
  const [lifecycleBusyId, setLifecycleBusyId] = React.useState<number | null>(null);
  const [eventHistory, setEventHistory] = React.useState<Record<number, Array<Record<string, unknown>>>>({});
  const [canReviewKnowledge, setCanReviewKnowledge] = React.useState(false);
  const [authenticated, setAuthenticated] = React.useState<boolean | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [message, setMessage] = React.useState('');
  const [family, setFamily] = React.useState('');
  const [identity, setIdentity] = React.useState('');
  const [query, setQuery] = React.useState('');
  const [queryDraft, setQueryDraft] = React.useState('');
  const [notes, setNotes] = React.useState<Record<number, string>>({});
  const [busyId, setBusyId] = React.useState<number | null>(null);
  const [usageEntryId, setUsageEntryId] = React.useState<number | null>(null);
  const [usageHistoryId, setUsageHistoryId] = React.useState('');
  const [usageOutcome, setUsageOutcome] = React.useState<'resolved' | 'partially_resolved' | 'not_resolved' | 'not_attempted'>('resolved');
  const [usageNotes, setUsageNotes] = React.useState('');
  const [usageBusy, setUsageBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // Application login is not used. Session is optional attribution only.
      const session = await fetch(apiUrl('/api/v1/auth/session'), { cache: 'no-store' });
      const sessionInfo = session.ok ? await json(session) : { capabilities: {} };
      setAuthenticated(true);
      const canReview = Boolean(sessionInfo.capabilities?.knowledge_review);
      setCanReviewKnowledge(canReview);
      const params = new URLSearchParams({ limit: '100' });
      if (family.trim()) params.set('source_family', family.trim());
      if (identity.trim()) params.set('diagnostic_identity', identity.trim());
      if (query.trim().length >= 2) params.set('q', query.trim());
      const published = await json(await fetch(apiUrl('/api/v1/knowledge/?' + params.toString()), { cache: 'no-store' }));
      setEntries(published.items || []);
      const sources = await json(await fetch(apiUrl('/api/v1/knowledge/sources?limit=100'), { cache: 'no-store' }));
      setSourceCandidates(sources.items || []);
      if (canReview) {
        const pending = await json(await fetch(apiUrl('/api/v1/knowledge/review-queue?limit=100'), { cache: 'no-store' }));
        setQueue(pending.items || []);
        const lifecycle = await json(await fetch(apiUrl('/api/v1/knowledge/lifecycle/review-queue?limit=100'), { cache: 'no-store' }));
        setLifecycleQueue(lifecycle.items || []);
      } else {
        setQueue([]); setLifecycleQueue([]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Knowledge could not be loaded');
    } finally { setLoading(false); }
  }, [family, identity, query]);

  React.useEffect(() => {
    const handle = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(handle);
  }, [load]);

  const reviewEntry = async (entry: Entry, decision: 'approve' | 'reject') => {
    if (busyId !== null) return;
    const note = notes[entry.id] || '';
    if (note.trim().length < 5) {
      setError('A review note of at least five characters is required to approve or reject an entry.'); return;
    }
    setBusyId(entry.id); setError(''); setMessage('');
    try {
      await json(await fetch(apiUrl(`/api/v1/knowledge/${entry.id}/review`), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, note }),
      }));
      setMessage(decision === 'approve'
        ? 'Knowledge approved and published for exact-identity reuse.'
        : 'Knowledge rejected and retained in the audit trail.');
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Review action failed');
    } finally { setBusyId(null); }
  };

  const changeLifecycle = async (
    entry: Entry,
    action: 'require_review' | 'revalidate' | 'supersede' | 'withdraw',
  ) => {
    if (lifecycleBusyId !== null) return;
    const reason = (lifecycleReasons[entry.id] || '').trim();
    const note = (lifecycleNotes[entry.id] || '').trim();
    const replacement = Number(replacementIds[entry.id]);
    if (reason.length < 3 || note.length < 5) {
      setError('Lifecycle reason (3+ characters) and reviewer note (5+ characters) are required.');
      return;
    }
    if (action === 'supersede' && (!Number.isInteger(replacement) || replacement <= 0)) {
      setError('Enter the ID of an active approved replacement with the same diagnostic identity.');
      return;
    }
    setLifecycleBusyId(entry.id); setError(''); setMessage('');
    try {
      await json(await fetch(apiUrl(`/api/v1/knowledge/${entry.id}/lifecycle`), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action, reason, note,
          ...(action === 'supersede' ? { superseded_by_id: replacement } : {}),
        }),
      }));
      setMessage(`Knowledge #${entry.id} lifecycle updated: ${action.replaceAll('_', ' ')}.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Lifecycle action failed');
    } finally { setLifecycleBusyId(null); }
  };

  const loadLifecycleEvents = async (entryId: number) => {
    try {
      const result = await json(await fetch(apiUrl(`/api/v1/knowledge/${entryId}/lifecycle/events`), { cache: 'no-store' }));
      setEventHistory((current) => ({ ...current, [entryId]: result.items || [] }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Lifecycle history could not be loaded');
    }
  };


  const reviewSource = async (
    candidate: SourceCandidate,
    decision: 'verify_reference' | 'reject' | 'require_revalidation' | 'withdraw',
  ) => {
    if (sourceBusyId !== null) return;
    const note = (sourceReviewNotes[candidate.id] || '').trim();
    if (note.length < 10) {
      setError('Domain review evidence must contain at least 10 characters.');
      return;
    }
    setSourceBusyId(candidate.id); setError(''); setMessage('');
    try {
      await json(await fetch(apiUrl(`/api/v1/knowledge/sources/${candidate.id}/review`), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, note }),
      }));
      setMessage(`Source ${candidate.sourceKey} review state updated: ${decision.replaceAll('_', ' ')}. This does not publish reusable Knowledge.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Source review failed');
    } finally { setSourceBusyId(null); }
  };

  const loadSourceEvents = async (sourceId: number) => {
    try {
      const result = await json(await fetch(apiUrl(`/api/v1/knowledge/sources/${sourceId}/events`), { cache: 'no-store' }));
      setSourceEvents((current) => ({ ...current, [sourceId]: result.items || [] }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Source audit history could not be loaded');
    }
  };

  const submitUsage = async (entryId: number) => {
    const historyId = Number(usageHistoryId);
    if (!Number.isInteger(historyId) || historyId <= 0) { setError('Enter a valid History ID owned by your account.'); return; }
    setUsageBusy(true); setError(''); setMessage('');
    try {
      await json(await fetch(apiUrl(`/api/v1/knowledge/${entryId}/usage`), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history_id: historyId, outcome: usageOutcome, notes: usageNotes }),
      }));
      const summary = await json(await fetch(apiUrl(`/api/v1/knowledge/${entryId}/usage-summary`), { cache: 'no-store' }));
      setMessage(`Outcome recorded. This knowledge has ${summary.total} reported use(s): ${summary.outcomes.resolved} resolved, ${summary.outcomes.partially_resolved} partial, ${summary.outcomes.not_resolved} not resolved.`);
      setUsageEntryId(null); setUsageHistoryId(''); setUsageNotes('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Outcome could not be recorded');
    } finally { setUsageBusy(false); }
  };

  const date = (value: string | null) => value ? new Date(value).toLocaleString() : '—';

  return (
    <main className="mx-auto w-full max-w-6xl p-4 md:p-6 space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-eims-text">Engineering Knowledge Base</h1>
          <a href="/knowledge/review" className="text-sm underline text-eims-text-secondary" data-testid="link-reviewer-workflow">Catalog candidate reviewer workflow</a>
          <p className="mt-1 text-sm text-eims-text-secondary">Human-reviewed incident lessons with provenance, resolution outcome and prevention guidance.</p>
        </div>
        <button onClick={() => void load()} disabled={loading} className="rounded-md border border-eims-border px-3 py-2 text-sm text-eims-text hover:bg-eims-surface-subtle disabled:opacity-50">Refresh</button>
      </header>

      {error && <div role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/5 p-3 text-sm text-rose-600 dark:text-rose-300">{error}</div>}
      {message && <div role="status" className="rounded-lg border border-eims-border bg-eims-surface p-3 text-sm text-eims-text">{message}</div>}

      <section className="rounded-lg border border-eims-border bg-eims-surface p-4">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_1.5fr_auto] gap-3 items-end">
          <label className="text-xs text-eims-text-secondary">Search approved knowledge
            <input value={queryDraft} onChange={(event) => setQueryDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') setQuery(queryDraft); }} placeholder="Search symptoms, error text, causes or fixes" className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
          </label>
          <label className="text-xs text-eims-text-secondary">Source family
            <select value={family} onChange={(event) => setFamily(event.target.value)} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text">
              <option value="">All families</option><option value="windows_event">Windows Event</option><option value="veeam_vbr">Veeam</option><option value="vmware">VMware</option><option value="fortinet">Fortinet</option><option value="cisco_asa">Cisco ASA</option><option value="palo_alto">Palo Alto</option><option value="linux_syslog">Linux Syslog</option><option value="json">JSON</option>
            </select>
          </label>
          <label className="text-xs text-eims-text-secondary">Diagnostic identity
            <input value={identity} onChange={(event) => setIdentity(event.target.value)} placeholder="e.g. 4625 or FGT-9001" className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
          </label>
          <button onClick={() => setQuery(queryDraft)} disabled={loading} className="rounded-md bg-eims-primary px-4 py-2 text-sm text-white disabled:opacity-50">Search</button>
        </div>
      </section>

      {canReviewKnowledge && <section className="space-y-3">
        <div className="flex items-center justify-between gap-2"><h2 className="text-lg font-semibold text-eims-text">Independent review queue</h2><span className="text-xs text-eims-text-secondary">{queue.length} pending</span></div>
        {queue.length === 0 && <p className="text-sm text-eims-text-secondary">No pending knowledge proposals.</p>}
        {queue.map((entry) => <article key={entry.id} className="rounded-lg border border-amber-500/30 bg-eims-surface p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold text-eims-text">{entry.title}</h3><p className="text-xs text-eims-text-secondary">{entry.sourceFamily} · {entry.diagnosticIdentity} · proposed by {entry.proposedBy}</p></div><span className="rounded border border-amber-500/40 px-2 py-1 text-xs text-amber-600 dark:text-amber-300">PENDING</span></div>
          <p className="text-sm text-eims-text">{entry.rootCause}</p>
          <ol className="list-decimal pl-5 text-sm text-eims-text-secondary space-y-1">{entry.solutionSteps.map((step, index) => <li key={index}>{step}</li>)}</ol>
          {entry.impact && <p className="text-sm text-eims-text-secondary"><strong>Impact:</strong> {entry.impact}</p>}
          {entry.prevention && <p className="text-sm text-eims-text-secondary"><strong>Prevention:</strong> {entry.prevention}</p>}
          <p className="text-xs text-eims-text-secondary"><strong>Applicability:</strong> {[entry.productName, entry.productVersion, entry.environment].filter(Boolean).join(' · ') || 'Not specified'} · <strong>Risk:</strong> {entry.riskLevel}</p>
          {entry.prerequisites.length > 0 && <p className="text-sm text-eims-text-secondary"><strong>Prerequisites:</strong> {entry.prerequisites.join(' · ')}</p>}
          {entry.validationSteps.length > 0 && <div className="text-sm text-eims-text-secondary"><strong>Validation:</strong><ol className="list-decimal pl-5">{entry.validationSteps.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
          {entry.rollbackSteps.length > 0 && <div className="text-sm text-eims-text-secondary"><strong>Rollback:</strong><ol className="list-decimal pl-5">{entry.rollbackSteps.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
          <ul className="list-disc pl-5 text-xs text-eims-text-secondary space-y-1">{entry.evidenceNotes.map((note, index) => <li key={index}>{note}</li>)}</ul>
          <p className="text-[11px] text-eims-text-muted">Source incident SHA-256: {entry.sourceHistoryHash}</p>
          <label className="block text-xs text-eims-text-secondary">Review note (required for approval or rejection)
            <textarea value={notes[entry.id] || ''} onChange={(event) => setNotes((current) => ({ ...current, [entry.id]: event.target.value }))} rows={2} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
          </label>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => void reviewEntry(entry, 'approve')} disabled={busyId !== null} className="rounded-md bg-emerald-700 px-3 py-2 text-xs font-medium text-white disabled:opacity-50">{busyId === entry.id ? 'Saving…' : 'Approve & publish'}</button>
            <button onClick={() => void reviewEntry(entry, 'reject')} disabled={busyId !== null} className="rounded-md border border-rose-500/50 px-3 py-2 text-xs font-medium text-rose-600 dark:text-rose-300 disabled:opacity-50">Reject</button>
          </div>
        </article>)}
      </section>}

      {canReviewKnowledge && <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-eims-text">Knowledge revalidation queue</h2>
          <span className="text-xs text-eims-text-secondary">{lifecycleQueue.length} awaiting revalidation</span>
        </div>
        {lifecycleQueue.length === 0 && <p className="text-sm text-eims-text-secondary">No entries currently require revalidation.</p>}
        {lifecycleQueue.map((entry) => <article key={entry.id} className="rounded-lg border border-orange-500/30 bg-eims-surface p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><h3 className="font-semibold text-eims-text">#{entry.id} · {entry.title}</h3><p className="text-xs text-eims-text-secondary">{entry.sourceFamily} · {entry.diagnosticIdentity}</p></div>
            <span className="rounded border border-orange-500/40 px-2 py-1 text-xs text-orange-600 dark:text-orange-300">REVALIDATION REQUIRED</span>
          </div>
          <p className="text-sm text-eims-text-secondary">{entry.lifecycleReason}</p>
          <div className="grid gap-2 md:grid-cols-2">
            <label className="text-xs text-eims-text-secondary">Review reason
              <input value={lifecycleReasons[entry.id] || ''} onChange={(event) => setLifecycleReasons((current) => ({ ...current, [entry.id]: event.target.value }))} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
            </label>
            <label className="text-xs text-eims-text-secondary">Reviewer note / evidence
              <input value={lifecycleNotes[entry.id] || ''} onChange={(event) => setLifecycleNotes((current) => ({ ...current, [entry.id]: event.target.value }))} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => void changeLifecycle(entry, 'revalidate')} disabled={lifecycleBusyId !== null} className="rounded-md bg-eims-primary px-3 py-2 text-xs text-white disabled:opacity-50">Revalidate & reactivate</button>
            <input aria-label="Replacement approved knowledge ID" type="number" min="1" placeholder="Replacement ID" value={replacementIds[entry.id] || ''} onChange={(event) => setReplacementIds((current) => ({ ...current, [entry.id]: event.target.value }))} className="w-36 rounded-md border border-eims-border bg-eims-bg px-2 py-2 text-xs text-eims-text" />
            <button onClick={() => void changeLifecycle(entry, 'supersede')} disabled={lifecycleBusyId !== null} className="rounded-md border border-eims-border px-3 py-2 text-xs text-eims-text disabled:opacity-50">Supersede</button>
            <button onClick={() => void changeLifecycle(entry, 'withdraw')} disabled={lifecycleBusyId !== null} className="rounded-md border border-rose-500/50 px-3 py-2 text-xs text-rose-600 dark:text-rose-300 disabled:opacity-50">Withdraw</button>
          </div>
        </article>)}
      </section>}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div><h2 className="text-lg font-semibold text-eims-text">Official vendor source catalogue</h2><p className="text-xs text-eims-text-secondary">Reference candidates only — never published as incident Knowledge or enabled for exact-identity remediation.</p></div>
          <span className="text-xs text-eims-text-secondary">{sourceCandidates.length} candidates loaded</span>
        </div>
        {sourceCandidates.length === 0 && <p className="rounded-lg border border-eims-border p-3 text-sm text-eims-text-secondary">No source candidates have been imported into this database yet. Run the guarded catalogue import after the schema migration.</p>}
        {sourceCandidates.map((candidate) => <article key={candidate.id} className="rounded-lg border border-eims-border bg-eims-surface p-4 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><h3 className="font-semibold text-eims-text">{candidate.vendor} · {candidate.title}</h3><p className="text-xs text-eims-text-secondary">{candidate.product} · {candidate.identity} · {candidate.domain}</p><p className="text-xs text-eims-text-muted">Catalogue key: {candidate.sourceKey} · Version scope: {candidate.versionScope}</p></div>
            <span className="rounded border border-eims-border px-2 py-1 text-xs text-eims-text-secondary">{candidate.reviewState.replaceAll('_', ' ').toUpperCase()}</span>
          </div>
          <p className="text-sm text-eims-text">{candidate.applicability}</p>
          <div className="grid gap-3 md:grid-cols-2 text-xs text-eims-text-secondary">
            <div><strong>Prerequisites</strong><ul className="list-disc pl-5">{candidate.prerequisites.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
            <div><strong>Evidence to collect</strong><ul className="list-disc pl-5">{candidate.evidence.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
            <div><strong>Limitations</strong><ul className="list-disc pl-5">{candidate.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
            <div><strong>Next checks</strong><ul className="list-disc pl-5">{candidate.nextChecks.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
            <div><strong>Validation</strong><ul className="list-disc pl-5">{candidate.validation.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
            <div><strong>Rollback boundaries</strong><ul className="list-disc pl-5">{candidate.rollback.map((item, i) => <li key={i}>{item}</li>)}</ul></div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-eims-text-secondary">
            <span>Risk: {candidate.riskLevel}</span><span>Evidence: {candidate.evidenceStatus}</span>
            <a href={candidate.url} target="_blank" rel="noreferrer" className="text-eims-accent underline break-all">Open official source</a>
          </div>
          <p className="break-all text-[11px] text-eims-text-muted">Catalogue record SHA-256 (not a downloaded Vendor document hash): {candidate.catalogueRecordHash}</p>
          {candidate.reviewedBy && <p className="text-xs text-eims-text-secondary">Last reviewed by {candidate.reviewedBy} · {date(candidate.reviewedAt)} · {candidate.reviewNote}</p>}
          <button onClick={() => void loadSourceEvents(candidate.id)} className="rounded-md border border-eims-border px-3 py-2 text-xs text-eims-text">Source audit history</button>
          {canReviewKnowledge && candidate.reviewState !== 'withdrawn' && <div className="space-y-2 border-t border-eims-border pt-3">
            <label className="block text-xs text-eims-text-secondary">Domain review evidence (required, minimum 10 characters)
              <textarea value={sourceReviewNotes[candidate.id] || ''} onChange={(event) => setSourceReviewNotes((current) => ({ ...current, [candidate.id]: event.target.value }))} rows={2} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
            </label>
            <div className="flex flex-wrap gap-2">
              {(candidate.reviewState === 'pending_domain_review' || candidate.reviewState === 'revalidation_required') && <>
                <button onClick={() => void reviewSource(candidate, 'verify_reference')} disabled={sourceBusyId !== null} className="rounded-md bg-eims-primary px-3 py-2 text-xs text-white disabled:opacity-50">Verify source reference</button>
                <button onClick={() => void reviewSource(candidate, 'reject')} disabled={sourceBusyId !== null} className="rounded-md border border-rose-500/50 px-3 py-2 text-xs text-rose-600 dark:text-rose-300 disabled:opacity-50">Reject candidate</button>
              </>}
              {candidate.reviewState === 'verified_reference' && <button onClick={() => void reviewSource(candidate, 'require_revalidation')} disabled={sourceBusyId !== null} className="rounded-md border border-orange-500/50 px-3 py-2 text-xs text-orange-600 dark:text-orange-300 disabled:opacity-50">Require revalidation</button>}
              <button onClick={() => void reviewSource(candidate, 'withdraw')} disabled={sourceBusyId !== null} className="rounded-md border border-eims-border px-3 py-2 text-xs text-eims-text disabled:opacity-50">Withdraw</button>
              
            </div>
          </div>}
          {sourceEvents[candidate.id] && <div className="rounded-md border border-eims-border p-3 text-xs text-eims-text-secondary space-y-2"><strong>Source audit history</strong>
            {sourceEvents[candidate.id].map((event, i) => <div key={String(event.id || i)} className="border-t border-eims-border pt-2"><p><strong>{String(event.fromState || 'imported')} → {String(event.toState)}</strong> · {String(event.action)} · {String(event.createdAt)}</p><p>{String(event.note)} · {String(event.changedBy)}</p></div>)}
          </div>}
        </article>)}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2"><h2 className="text-lg font-semibold text-eims-text">Approved knowledge</h2><span className="text-xs text-eims-text-secondary">{entries.length} entries</span></div>
        {loading && <p className="text-sm text-eims-text-secondary">Loading knowledge…</p>}
        {!loading && authenticated && entries.length === 0 && <p className="rounded-lg border border-eims-border bg-eims-surface p-4 text-sm text-eims-text-secondary">No approved entries match this filter yet. Proposals remain private until an independent reviewer approves them.</p>}
        {entries.map((entry) => <article key={entry.id} className="rounded-lg border border-eims-border bg-eims-surface p-4 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold text-eims-text">{entry.title}</h3><p className="text-xs text-eims-text-secondary">{entry.sourceFamily} · {entry.diagnosticIdentity} · {entry.resolutionStatus.replaceAll('_', ' ')}</p></div><span className="rounded border border-emerald-500/40 px-2 py-1 text-xs text-emerald-600 dark:text-emerald-300">APPROVED</span></div>
          <div><h4 className="text-xs font-semibold uppercase text-eims-text-muted">Root cause</h4><p className="mt-1 text-sm text-eims-text">{entry.rootCause}</p></div>
          <div><h4 className="text-xs font-semibold uppercase text-eims-text-muted">Resolution</h4><ol className="mt-1 list-decimal pl-5 text-sm text-eims-text-secondary space-y-1">{entry.solutionSteps.map((step, index) => <li key={index}>{step}</li>)}</ol></div>
          {entry.impact && <p className="text-sm text-eims-text-secondary"><strong>Impact:</strong> {entry.impact}</p>}
          {entry.prevention && <p className="text-sm text-eims-text-secondary"><strong>Prevention:</strong> {entry.prevention}</p>}
          <p className="text-xs text-eims-text-secondary"><strong>Applicability:</strong> {[entry.productName, entry.productVersion, entry.environment].filter(Boolean).join(' · ') || 'Not specified'} · <strong>Risk:</strong> {entry.riskLevel}</p>
          {entry.prerequisites.length > 0 && <p className="text-sm text-eims-text-secondary"><strong>Prerequisites:</strong> {entry.prerequisites.join(' · ')}</p>}
          {entry.validationSteps.length > 0 && <div className="text-sm text-eims-text-secondary"><strong>Validation:</strong><ol className="list-decimal pl-5">{entry.validationSteps.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
          {entry.rollbackSteps.length > 0 && <div className="text-sm text-eims-text-secondary"><strong>Rollback:</strong><ol className="list-decimal pl-5">{entry.rollbackSteps.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
          <ul className="list-disc pl-5 text-xs text-eims-text-secondary space-y-1">{entry.evidenceNotes.map((note, index) => <li key={index}>{note}</li>)}</ul>
          {entry.references.length > 0 && <div className="text-xs space-y-1"><h4 className="font-semibold text-eims-text-muted">References</h4>{entry.references.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer" className="block text-eims-accent underline break-all">{url}</a>)}</div>}
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => { setUsageEntryId(usageEntryId === entry.id ? null : entry.id); setError(''); }} className="rounded-md border border-eims-border px-3 py-2 text-xs text-eims-text">Report use outcome</button>
            <button onClick={() => void loadLifecycleEvents(entry.id)} className="rounded-md border border-eims-border px-3 py-2 text-xs text-eims-text">Lifecycle audit history</button>
          </div>
          {eventHistory[entry.id] && <div className="rounded-md border border-eims-border p-3 text-xs text-eims-text-secondary space-y-2">
            <strong>Lifecycle audit history</strong>
            {eventHistory[entry.id].length === 0 && <p>No lifecycle transitions recorded.</p>}
            {eventHistory[entry.id].map((event, index) => <div key={String(event.id || index)} className="border-t border-eims-border pt-2">
              <p><strong>{String(event.fromState || 'created')} → {String(event.toState)}</strong> · {String(event.action)} · {String(event.createdAt)}</p>
              <p>{String(event.reason)} — {String(event.note)} · {String(event.changedBy)}</p>
            </div>)}
          </div>}
          {canReviewKnowledge && <div className="rounded-md border border-eims-border p-3 space-y-2">
            <p className="text-xs font-semibold text-eims-text">Reviewer lifecycle controls</p>
            <div className="grid gap-2 md:grid-cols-2">
              <label className="text-xs text-eims-text-secondary">Reason
                <input value={lifecycleReasons[entry.id] || ''} onChange={(event) => setLifecycleReasons((current) => ({ ...current, [entry.id]: event.target.value }))} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
              </label>
              <label className="text-xs text-eims-text-secondary">Reviewer note / evidence
                <input value={lifecycleNotes[entry.id] || ''} onChange={(event) => setLifecycleNotes((current) => ({ ...current, [entry.id]: event.target.value }))} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => void changeLifecycle(entry, 'require_review')} disabled={lifecycleBusyId !== null} className="rounded-md border border-orange-500/50 px-3 py-2 text-xs text-orange-600 dark:text-orange-300 disabled:opacity-50">Require revalidation</button>
              <button onClick={() => void changeLifecycle(entry, 'withdraw')} disabled={lifecycleBusyId !== null} className="rounded-md border border-rose-500/50 px-3 py-2 text-xs text-rose-600 dark:text-rose-300 disabled:opacity-50">Withdraw</button>
            </div>
          </div>}
          {usageEntryId === entry.id && <form onSubmit={(event) => { event.preventDefault(); void submitUsage(entry.id); }} className="rounded-md border border-eims-border p-3 space-y-2">
            <label className="block text-xs text-eims-text-secondary">Your EIMS History ID
              <input type="number" min="1" required value={usageHistoryId} onChange={(event) => setUsageHistoryId(event.target.value)} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
            </label>
            <label className="block text-xs text-eims-text-secondary">Outcome
              <select value={usageOutcome} onChange={(event) => setUsageOutcome(event.target.value as typeof usageOutcome)} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text">
                <option value="resolved">Resolved</option><option value="partially_resolved">Partially resolved</option><option value="not_resolved">Not resolved</option><option value="not_attempted">Not attempted</option>
              </select>
            </label>
            <label className="block text-xs text-eims-text-secondary">Outcome notes (sanitized; no secrets or raw customer logs)
              <textarea value={usageNotes} onChange={(event) => setUsageNotes(event.target.value)} rows={2} maxLength={2000} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg p-2 text-sm text-eims-text" />
            </label>
            <button type="submit" disabled={usageBusy} className="rounded-md bg-eims-primary px-3 py-2 text-xs text-white disabled:opacity-50">{usageBusy ? 'Saving…' : 'Record outcome'}</button>
          </form>}
          <div className="border-t border-eims-border pt-2 text-[11px] text-eims-text-muted">Reviewed by {entry.reviewedBy || '—'} · {date(entry.reviewedAt)} · Source SHA-256 {entry.sourceHistoryHash}</div>
        </article>)}
      </section>
    </main>
  );
}
