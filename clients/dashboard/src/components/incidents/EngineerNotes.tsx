"use client";

/**
 * Engineer Notes — real Incident Core API.
 * Contract (Claude): GET/POST /api/v1/incidents/{id}/notes
 * Body create: { text } only. Actor, assurance, timestamps are server-derived.
 * Observations only — never diagnosis / verification / resolution.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "@/lib/api";
import { ASSURANCE_SHORT, ASSURANCE_LONG, btn, field, json } from "./shared";

export type EngineerNote = {
  note_id: string;
  text: string;
  created_at: string;
  actor: string;
  actor_assurance: string;
};

export type EngineerNotesProps = {
  incidentId: string;
  /** When false, show honest gap (no browser persistence). Default true once Notes API is verified. */
  apiEnabled?: boolean;
};

function when(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function normalizeNotes(rows: unknown): EngineerNote[] {
  const list = Array.isArray(rows) ? rows : (rows as { items?: unknown })?.items;
  if (!Array.isArray(list)) return [];
  return list
    .map((row) => {
      const r = row as Record<string, unknown>;
      const note_id = typeof r.note_id === "string" ? r.note_id : String(r.note_id ?? "");
      const text = typeof r.text === "string" ? r.text : "";
      const created_at = typeof r.created_at === "string" ? r.created_at : "";
      const actor = typeof r.actor === "string" ? r.actor : "—";
      const actor_assurance = typeof r.actor_assurance === "string" ? r.actor_assurance : "";
      if (!note_id || !text) return null;
      return { note_id, text, created_at, actor, actor_assurance };
    })
    .filter((n): n is EngineerNote => n != null);
}

export default function EngineerNotes({ incidentId, apiEnabled = true }: EngineerNotesProps) {
  const [notes, setNotes] = useState<EngineerNote[] | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const latest = useRef(0);
  const submitting = useRef(false);

  const load = useCallback(async () => {
    if (!apiEnabled || !incidentId) return;
    const token = ++latest.current;
    setBusy(true);
    setError("");
    try {
      const rows = await fetch(
        apiUrl(`/api/v1/incidents/${incidentId}/notes?limit=50&offset=0`),
        { cache: "no-store" },
      ).then(json);
      if (token !== latest.current) return;
      setNotes(normalizeNotes(rows));
      setLoaded(true);
    } catch (cause) {
      if (token !== latest.current) return;
      setNotes(null);
      setLoaded(true);
      setError(cause instanceof Error ? cause.message : "Notes could not be loaded");
    } finally {
      if (token === latest.current) setBusy(false);
    }
  }, [apiEnabled, incidentId]);

  // Host remounts with key={incidentId}; token still guards in-flight responses.
  useEffect(() => {
    if (!apiEnabled || !incidentId) return;
    const t = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(t);
  }, [apiEnabled, incidentId, load]);

  const add = async () => {
    const body = text.trim();
    if (!apiEnabled || !body || busy || submitting.current) return;
    if (body.length > 4000) {
      setError("Note must be at most 4000 characters.");
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await fetch(apiUrl(`/api/v1/incidents/${incidentId}/notes`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: body }),
      }).then(json);
      setText("");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Note was not saved");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Engineer Notes"
      className="bg-eims-surface border border-eims-border rounded-lg p-4 space-y-2"
      data-testid="engineer-notes"
    >
      <h3 className="text-sm font-semibold text-eims-text">Engineer Notes</h3>
      <p className="text-xs text-eims-text-muted">
        Observations only — not a confirmed diagnosis, verification, or resolution.
        Actor and assurance come from the server.
      </p>

      {!apiEnabled ? (
        <div className="text-xs text-eims-text-secondary space-y-1" data-testid="engineer-notes-gap">
          <p>
            Notes API is not enabled in this build. Nothing is stored in the browser.
          </p>
        </div>
      ) : (
        <>
          {!loaded && busy ? (
            <p className="text-xs text-eims-text-muted" data-testid="engineer-notes-loading">Loading notes…</p>
          ) : null}
          {error ? (
            <div className="space-y-1" role="alert">
              <p className="text-xs text-red-600">{error}</p>
              <button type="button" className={btn} disabled={busy} onClick={() => void load()}>
                Retry
              </button>
            </div>
          ) : null}
          {loaded && !error && notes && notes.length === 0 ? (
            <p className="text-xs text-eims-text-muted" data-testid="engineer-notes-empty">No notes yet.</p>
          ) : null}
          {notes && notes.length > 0 ? (
            <ul className="space-y-2" data-testid="engineer-notes-list">
              {notes.map((n) => (
                <li key={n.note_id} className="text-sm border-l-2 border-eims-border pl-3">
                  <p className="text-eims-text whitespace-pre-wrap break-words">{n.text}</p>
                  <p
                    className="text-[11px] text-eims-text-muted mt-0.5"
                    title={ASSURANCE_LONG[n.actor_assurance] || n.actor_assurance}
                  >
                    {when(n.created_at)}
                    {" · "}
                    {n.actor_assurance === "unattributed"
                      ? `${n.actor} (unattributed — not a verified person)`
                      : `${n.actor} · ${ASSURANCE_SHORT[n.actor_assurance] || n.actor_assurance}`}
                  </p>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="space-y-1 pt-1">
            <label className="block text-xs text-eims-text-secondary" htmlFor={`note-${incidentId}`}>
              Add note
            </label>
            <textarea
              id={`note-${incidentId}`}
              className={field}
              rows={2}
              maxLength={4000}
              value={text}
              disabled={busy}
              onChange={(e) => setText(e.target.value)}
              placeholder="Observation only — e.g. DC02 responds normally"
            />
            <button
              type="button"
              className={btn}
              disabled={busy || !text.trim()}
              onClick={() => void add()}
              data-testid="engineer-notes-submit"
            >
              {busy ? "Saving…" : "Add Note"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
