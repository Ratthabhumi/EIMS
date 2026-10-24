"""Real Analyzer route orchestration with explicit offline/in-memory dependencies.

Not an HTTP/auth or PostgreSQL test. No operational session is ever supplied.
"""
import asyncio
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
import io
import json
import re
from pathlib import Path
from unittest.mock import patch

from evaluation.analyzer.runner import offline_guard, predict as stage_predict


class MemoryHistory:
    """Narrow isolated sink for existing route/history service contracts."""
    def __init__(self, rows=None):
        self.rows = rows or []
        self.commits = 0

    def add(self, obj):
        self.rows.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        obj.id = len(self.rows)
        obj.created_at = datetime(2026, 10, 25)

    async def execute(self, query):
        return self

    def scalars(self):
        return self

    def all(self):
        return self.rows


def json_value(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=lambda o:
                                o.model_dump() if hasattr(o, "model_dump") else o.isoformat()))


def snapshot(row):
    # Operational timing is not part of deterministic semantic identity.
    fields = ("id", "event_id", "provider", "parse_method", "description", "ai_summary",
              "solution_summary", "event_metadata", "search_results", "username", "created_at")
    return json_value({k: getattr(row, k) for k in fields})


def make_claims(response, files):
    summary = response["solutionSummary"]
    meta = response["eventMetadata"]
    refs = []
    names = {Path(n).name: n for n in files}
    if len(names) != len(files):
        raise ValueError("ambiguous upload basenames; no invented source mapping")
    for e in summary.get("evidenceItems", []):
        file = names.get(e["sourceFile"])
        if file:
            lines = files[file][1].splitlines()
            line = e["lineNumber"]
            valid = 1 <= line <= len(lines) and lines[line - 1].strip()[:500] == e["message"]
            refs.append({"file": file, "line": line, "message": e["message"],
                         "coordinate_valid": valid, "origin": "native_bundle_citation"})
    # Single-file route may emit a literal signature rather than a full line.
    # Resolve only one exact occurrence, record its character span and preserve
    # the actual raw line. Never fuzzy-match, guess a file or infer semantic support.
    unresolved = []
    if not summary.get("evidenceItems"):
        for text in summary.get("evidence", []):
            matches = [(name, i, line.index(text), line) for name, (_, raw) in files.items()
                       for i, line in enumerate(raw.splitlines(), 1) if text and line.count(text) == 1]
            if len(matches) == 1:
                name, number, start, raw_line = matches[0]
                refs.append({"file": name, "line": number, "message": raw_line,
                             "quoted_excerpt": text, "span_start": start, "span_end": start + len(text),
                             "coordinate_valid": True, "origin": "unique_exact_literal_citation_span"})
            else:
                unresolved.append({"text": text, "reason": "SOURCE_LINE_AMBIGUOUS_OR_UNAVAILABLE"})
    claims = []
    def add(cid, text, category, evidence_type, evidence=None):
        if not text or not text.strip():
            return
        claims.append({"claim_id": cid, "text": text, "category": category,
                       "evidence_type": evidence_type, "evidence": evidence or [],
                       "support_judgment": "NOT_REVIEWED", "reviewer": None, "rationale": None})
    add("overview", summary.get("overview", ""), "UNCERTAIN", "RCA_OVERVIEW", refs)
    for i, r in enumerate(refs):
        role = "SEVERITY" if re.match(r"^\s*Level\s*:", r["message"], re.I) else "FAILURE_DESCRIPTION"
        if "CTK_CTKUNLINK" in r["message"]:
            role = "TECHNICAL_FAILURE"
        add(f"observed-{i}", r["message"], "DIRECTLY_OBSERVED", role, [r])
    # Metadata fields rendered by the native API also need their own support
    # role. These are declared source projections, not invented native finding
    # citations, and never support a detailed root-cause claim automatically.
    if meta.get("sourceFamily") == "windows_event":
        for file_index, (name, (_, raw)) in enumerate(sorted(files.items())):
            for line, text in enumerate(raw.splitlines(), 1):
                role = "EVENT_IDENTITY" if re.match(r"^\s*Event\s*ID\s*:", text, re.I) else "SEVERITY" if re.match(r"^\s*Level\s*:", text, re.I) else None
                if role:
                    add(f"metadata-{file_index}-{line}", text, "DIRECTLY_OBSERVED", role,
                        [{"file": name, "line": line, "message": text, "coordinate_valid": True,
                          "origin": "native_metadata_to_source_projection"}])
    for key, category, role in (("causes", "HYPOTHESIS", "POSSIBLE_CAUSE"),
                                ("steps", "UNCERTAIN", "RECOMMENDATION"),
                                ("limitations", "UNCERTAIN", "UNKNOWN"),
                                ("nextEvidence", "UNCERTAIN", "EVIDENCE_COLLECTION")):
        for i, text in enumerate(summary.get(key, [])):
            add(f"{key}-{i}", text, category, role)
    return claims, refs, unresolved


def predict_full(case, files):
    """Call actual submit_analysis/submit_bundle and get_all_history functions."""
    if any(Path(n).suffix.lower() not in {".txt", ".log"} for n in files):
        raise ValueError("full offline parity currently supports UTF-8 plaintext only")
    # Reuse stage adapter for baseline comparison, not a substitute for the
    # native response. All user-facing synthesis below is executed by the route.
    with offline_guard():
        baseline = stage_predict(case, files, "rule_kb")
    # Windows asyncio creates a local wakeup socketpair during loop startup.
    # Initialize that OS IPC before installing the strict network guard; all
    # imports and business logic still execute with outbound sockets blocked.
    with asyncio.Runner() as loop_runner, offline_guard():
        from fastapi import UploadFile
        from backend.api.routers.analyzer import analyze as api
        from backend.api.routers.analyzer import history
        from backend.domain.analyzer.models.history import AnalysisHistory
        from backend.domain.analyzer.services import summary, vector_db, event_knowledge
        from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results

        trace = [{"stage": "offline_dependencies", "history": "in_memory_only", "language": "en"}]
        async def no_rag(*args, **kwargs):
            trace.append({"stage": "RAG_disabled_by_injection"})
            return []
        async def no_export(*args, **kwargs):
            trace.append({"stage": "vector_export_disabled_by_injection"})
            return None
        def forbidden(*args, **kwargs):
            raise RuntimeError("EXTERNAL_COMPONENT_FORBIDDEN_IN_FULL_EVALUATION")
        def local_refs(event_id, provider, **kwargs):
            trace.append({"stage": "local_vendor_reference_retrieval"})
            results = vendor_reference_results(kwargs.get("diagnostic_code") or "", kwargs.get("evidence_text") or "", "en")
            return results, "\n".join(r.snippet for r in results)
        real_build = summary.build_summary
        async def real_synthesis(*args, **kwargs):
            trace.append({"stage": "production.build_summary"})
            return await real_build(*args, **kwargs)
        def trace_function(function, label):
            def call(*args, **kwargs):
                result = function(*args, **kwargs)
                trace.append({"stage": label, "returned_summary": result is not None})
                return result
            return call
        async def execute():
            sink = MemoryHistory()
            uploads = [UploadFile(file=io.BytesIO(raw), filename=Path(name).name)
                       for name, (raw, _) in sorted(files.items())]
            kwargs = dict(language="en", db=sink, _user="synthetic-evaluation", x_gemini_api_key=None)
            if len(uploads) == 1:
                trace.append({"stage": "production.submit_analysis"})
                response = await api.submit_analysis(text=None, file=uploads[0], **kwargs)
            else:
                trace.append({"stage": "production.submit_bundle"})
                response = await api.submit_bundle(files=uploads, **kwargs)
            saved = snapshot(sink.rows[0])
            # Serialization/reload is into a NEW memory sink, never PostgreSQL.
            reloaded = dict(saved)
            reloaded["created_at"] = datetime.fromisoformat(reloaded["created_at"])
            memory_reload = MemoryHistory([AnalysisHistory(**reloaded)])
            trace.append({"stage": "production.get_all_history", "storage": "serialized_memory_snapshot"})
            reopened = await history.get_all_history(db=memory_reload, _user="synthetic-evaluation", asset_id=None)
            native = response.model_dump()
            restored = json_value(reopened[0])
            if restored["solutionSummary"] != native["solutionSummary"] or restored["eventMetadata"] != native["eventMetadata"]:
                raise ValueError("isolated History roundtrip changed investigation")
            return native, saved, restored, sink.commits

        with ExitStack() as stack:
            # Curated objects are mutable in the existing implementation. Each
            # case receives a pristine deep copy; this isolation is declared,
            # not silently presented as a production cache fix.
            stack.enter_context(patch.dict(event_knowledge.EVENT_KNOWLEDGE, deepcopy(event_knowledge.EVENT_KNOWLEDGE), clear=True))
            stack.enter_context(patch.object(api, "search_solutions", local_refs))
            stack.enter_context(patch.object(api, "build_summary", real_synthesis))
            stack.enter_context(patch.object(summary, "search_similar_logs", no_rag))
            stack.enter_context(patch.object(vector_db, "add_solution", no_export))
            stack.enter_context(patch.object(vector_db, "_get_embedding", forbidden))
            stack.enter_context(patch.object(summary, "_call_gemini", forbidden))
            stack.enter_context(patch.object(summary, "get_vendor_summary", trace_function(summary.get_vendor_summary, "deterministic_vendor_summary")))
            stack.enter_context(patch.object(summary, "get_curated_summary", trace_function(summary.get_curated_summary, "curated_event_summary")))
            stack.enter_context(patch.object(summary, "_build_from_web", trace_function(summary._build_from_web, "offline_fallback_synthesis")))
            native, saved, reopened, commits = loop_runner.run(execute())

    claims, refs, unresolved = make_claims(native, files)
    result = deepcopy(baseline)
    result["stage_comparison"] = {k: baseline[k] for k in ("source_family", "diagnostic_code", "incident", "evidence")}
    result["native_response"] = native
    result["source_family"] = native["eventMetadata"]["sourceFamily"]
    result["evidence"] = refs
    result["claims"] = claims
    result["unresolved_citations"] = unresolved
    result["isolated_history_snapshot"] = saved
    result["reopened_isolated_history"] = reopened
    result["isolated_history_roundtrip"] = True
    result["history_sink_commits"] = commits
    result["investigation_trace"] = trace
    result["rca"] = {"overview": native["solutionSummary"]["overview"],
                     "confirmed_facts": [c for c in claims if c["category"] == "DIRECTLY_OBSERVED"],
                     "hypotheses": native["solutionSummary"].get("causes", []),
                     "unknowns": native["solutionSummary"].get("limitations", []),
                     "recommendations": native["solutionSummary"].get("steps", []),
                     "suggested_evidence": native["solutionSummary"].get("nextEvidence", []),
                     "root_cause_status": "UNKNOWN"}
    result["bypassed"] = ["real_HTTP_auth_transport", "PostgreSQL", "live_vector", "RAG", "Gemini", "external_web", "translation_network"]
    result["isolation_policy"] = "actual production route/synthesis/History serialization; memory sink; pristine curated cache per case; no operational persistence"
    return result
