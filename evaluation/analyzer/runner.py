"""Offline adapter to existing Analyzer stages; never import HTTP/DB/vector code."""
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import csv
import hashlib
import importlib.metadata
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import platform
import socket
import subprocess
import time
from unittest.mock import patch

from evaluation.analyzer.scoring import score

REPO = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def annotation_digest(case):
    return digest({k: v for k, v in case.items() if k not in {"review_status", "annotator_id", "reviewer_id", "reviewed_annotation_sha256"}})


def safe_input(base, name):
    p = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or p.is_absolute() or ".." in p.parts:
        raise ValueError("unsafe input path")
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError("input escapes corpus or is missing")
    return path


def normalized(text):
    # Only whitespace/case normalization; exact same incident IDs still leak.
    return " ".join(text.casefold().split())


def load_manual_reviews(path, predictions):
    if path is None:
        return {"claims": [], "citations": []}
    import jsonschema
    doc = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((REPO / "evaluation/analyzer/manual_reviews.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(doc)
    except jsonschema.ValidationError as exc:
        raise ValueError("manual-review schema violation at " + "/".join(map(str, exc.absolute_path))) from exc
    lookup = {p["case_id"]: p for p in predictions}
    seen = set()
    for category, rows in doc.items():
        for r in rows:
            p = lookup.get(r["case_id"])
            if not p or p.get("prediction_sha256") != r["prediction_sha256"]:
                raise ValueError("manual review references missing/stale prediction")
            if not r["reviewer_id"].strip() or not r["rationale"].strip() or r["reviewer_id"].strip().lower().startswith(("ai", "codex")):
                raise ValueError("manual support review requires human reviewer")
            key = (category, r["case_id"], r["item_id"])
            if key in seen:
                raise ValueError("duplicate manual review item")
            seen.add(key)
            if r["text"] not in json.dumps(p, ensure_ascii=False):
                raise ValueError("manual claim text is not present in prediction")
            if category == "citations" and not any(
                e["file"] == r["file"] and e["line"] == r["line"] for e in p.get("evidence", [])
            ):
                raise ValueError("manual review citation was not emitted")
    return doc


def load_manifest(path):
    import jsonschema
    doc = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(path.with_name("manifest.v1.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(doc)
    except jsonschema.ValidationError as exc:
        raise ValueError("manifest schema violation at " + "/".join(map(str, exc.absolute_path))) from exc
    ids, groups, exact, norm = set(), {}, {}, {}
    payloads = {}
    for c in doc["cases"]:
        cid = c["case_id"]
        if cid in ids:
            raise ValueError("duplicate case_id")
        ids.add(cid)
        group = c["scenario_group"]
        if group in groups and groups[group] != c["split"]:
            raise ValueError("scenario-group split leakage")
        groups[group] = c["split"]
        if c["review_status"] == "REVIEWED":
            if not (c.get("reviewer_id") or "").strip() or c["reviewer_id"].strip().lower().startswith(("ai", "codex")):
                raise ValueError("REVIEWED requires recorded human reviewer")
            if c.get("reviewed_annotation_sha256") != annotation_digest(c):
                raise ValueError("review receipt does not bind current annotation")
        files = {}
        if len({f["path"] for f in c["files"]}) != len(c["files"]):
            raise ValueError("duplicate file path in case")
        for f in c["files"]:
            raw = safe_input(path.parent, f["path"]).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            if sha != f["sha256"]:
                raise ValueError("input SHA-256 mismatch: " + cid)
            text = raw.decode("utf-8", errors="strict")
            for table, key in ((exact, sha), (norm, normalized(text))):
                if key in table and table[key] != c["split"]:
                    raise ValueError("duplicate-content split leakage")
                table[key] = c["split"]
            files[f["path"]] = (raw, text)
        truth = c["truth"]
        refs = truth["evidence"] + [truth[k] for k in ("first_failure", "terminal_failure") if truth.get(k)]
        for ref in refs:
            if ref["file"] not in files or not 1 <= ref["line"] <= ref.get("end_line", ref["line"]) <= len(files[ref["file"]][1].splitlines()):
                raise ValueError("invalid truth span: " + cid)
        seen_pairs = set()
        for pair in truth["correlation_pairs"]:
            key = tuple(sorted((pair["a"], pair["b"])))
            if pair["a"] == pair["b"] or not set(key) <= files.keys() or key in seen_pairs:
                raise ValueError("invalid/duplicate truth pair")
            seen_pairs.add(key)
        expected_pairs = len(files) * (len(files) - 1) // 2
        if len(seen_pairs) != expected_pairs:
            raise ValueError("every unordered bundle pair must be labeled")
        payloads[cid] = files
    # Freeze truth+inputs, not review metadata; human review may be added later.
    frozen = {c["case_id"]: annotation_digest(c) for c in doc["cases"] if c["split"] == "heldout"}
    lock = path.with_name("heldout.v1.lock.json")
    if frozen and (not lock.exists() or json.loads(lock.read_text(encoding="utf-8")) != frozen):
        raise ValueError("heldout annotations differ from immutable lock")
    # Compare with existing regression fixture literals, without importing tests.
    # Substring matching excludes direct copied fixtures from heldout; semantic
    # independence still needs human review, not this automated check.
    regression = (REPO / "tests/test_analyzer_reliability.py").read_text(encoding="utf-8")
    for c in doc["cases"]:
        if c["split"] == "heldout":
            for _, text in payloads[c["case_id"]].values():
                if len(text.strip()) >= 40 and normalized(text) in normalized(regression):
                    raise ValueError("heldout copies regression content")
    return doc, payloads


@contextmanager
def offline_guard():
    def blocked(*args, **kwargs):
        raise RuntimeError("NETWORK_DISABLED_IN_EVALUATION")
    with patch.object(socket.socket, "connect", blocked), patch.object(socket.socket, "connect_ex", blocked), patch.object(socket.socket, "sendto", blocked), \
            patch.object(socket, "create_connection", blocked), patch.object(socket, "getaddrinfo", blocked):
        yield


def predict(case, files, mode):
    from backend.domain.analyzer.services.parser import parse_event_metadata
    from backend.domain.analyzer.services.evidence import build_evidence_records
    from backend.domain.analyzer.services.incident_extract import incident_from_records
    from backend.domain.analyzer.services.bundle import summarize_file_evidence, build_evidence_items, correlate_bundle
    trace = []
    entries, meta = [], {}
    for name, (raw, text) in sorted(files.items()):
        m = parse_event_metadata(text, filename_hint=Path(name).name)
        meta[name] = m
        trace.append({"stage": "parse_event_metadata", "file": name})
        entries.append(summarize_file_evidence(name, raw, text, m.sourceFamily, m.product, m.diagnosticCode, m.parserConfidence))
    primary = case["files"][0]["path"]
    m = meta[primary]
    family = m.sourceFamily or "unknown_text"
    code = m.diagnosticCode or (m.eventId if family in {"windows_event", "fortinet", "cisco_asa"} and m.eventId not in {"Unknown", ""} else None)
    records = build_evidence_records([(name, value[1]) for name, value in sorted(files.items())])
    trace.append({"stage": "build_evidence_records"})
    incident = incident_from_records(records, family)
    trace.append({"stage": "incident_from_records"})
    items = build_evidence_items(entries)
    trace.append({"stage": "build_evidence_items"})
    def refs_for(text):
        if not text:
            return []
        return [{"file": r.source_file, "line": r.line_number}
                for r in records if r.raw_text == text]
    refs = []
    for item in items:
        name, line = item["sourceFile"], item["lineNumber"]
        lines = files[name][1].splitlines() if name in files else []
        valid = 1 <= line <= len(lines) and item["message"] == lines[line - 1].strip()[:500]
        refs.append({"file": name, "line": line, "message": item["message"], "coordinate_valid": valid})
    pairs = []
    for a, b in itertools.combinations(entries, 2):
        result = correlate_bundle([a, b])
        trace.append({"stage": "correlate_bundle", "files": [a.filename, b.filename]})
        confidence = result["correlationConfidence"]
        pairs.append({"a": a.filename, "b": b.filename, "related": confidence in {"strong", "medium"},
                      "confidence": confidence, "reasons": result["correlationReasons"], "causation_proven": False})
    kb = []
    if mode == "rule_kb":
        from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
        # Call per-file to preserve operation-local applicability gates.
        for name, (_, text) in sorted(files.items()):
            kb.extend(r.link for r in vendor_reference_results(meta[name].diagnosticCode, text, "en"))
            trace.append({"stage": "vendor_reference_results", "file": name})
    return {"case_id": case["case_id"], "status": "OK", "source_family": family,
            "primary_file": primary, "per_file_metadata": {k: v.model_dump() for k, v in sorted(meta.items())},
            "diagnostic_code": code, "identity_abstained": code is None,
            "first_failure": refs_for(incident["firstMeaningfulFailure"]),
            "terminal_failure": refs_for(incident["terminalFailure"]),
            "incident": incident, "evidence": refs, "correlation_pairs": pairs,
            "kb": sorted(set(kb)), "kb_executed": mode == "rule_kb", "trace": trace,
            "bypassed": ["HTTP", "History", "DB", "vector", "RAG", "Gemini", "web", "build_summary"]}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def validate_output(output):
    if output.exists():
        raise ValueError("output already exists; immutable run directories only")
    resolved = output.resolve()
    if not any(resolved.is_relative_to((REPO / allowed).resolve())
               for allowed in ("evaluation/analyzer/results", "test-results")):
        raise ValueError("output must stay in repository evaluation results or test-results")
    return resolved


def run(manifest, mode, split, output, include_draft=False, repeats=3, warmups=3, manual_review_path=None, annotations_v2=None, grounding_reviews=None):
    if repeats < 1 or warmups < 0:
        raise ValueError("repeats must be positive and warmups nonnegative")
    if mode not in {"rule_only", "rule_kb", "full_investigation"}:
        raise ValueError("NOT_RUN: RAG/LLM modes are not isolated or authorized")
    doc, payloads = load_manifest(manifest)
    semantics = {}
    if annotations_v2:
        from evaluation.analyzer.semantics_v2 import load_annotations
        _, semantics = load_annotations(annotations_v2, manifest, doc["cases"])
        if split != "dev":
            raise ValueError("v2 migration is DEV-only; v1 heldout lock is preserved")
    cases = sorted([c for c in doc["cases"] if c["split"] == split and
                    (not semantics or c["case_id"] in semantics) and
                    (include_draft or semantics.get(c["case_id"], c)["review_status"] == "REVIEWED")], key=lambda c: c["case_id"])
    if split == "heldout" and any(c["review_status"] != "REVIEWED" for c in cases):
        raise ValueError("heldout execution requires human-reviewed labels; DRAFT is reserved")
    resolved = validate_output(output)
    if any(resolved.is_relative_to(safe_input(manifest.parent, f["path"])) for c in doc["cases"] for f in c["files"]):
        raise ValueError("output collides with input")
    config = {"schema_version": "1.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "analyzer_git_sha": git("rev-parse", "HEAD"), "source_commit_declared": doc["source_commit"],
              "analyzer_tree_sha": git("rev-parse", "HEAD:backend/domain/analyzer"),
              "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
              "annotation_sha256": {c["case_id"]: annotation_digest(c) for c in cases},
              "scorer_sha256": hashlib.sha256(Path(__file__).with_name("scoring.py").read_bytes()).hexdigest(),
              "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "git_dirty": bool(git("status", "--porcelain")), "mode": mode, "split": split,
              "include_draft": include_draft, "warmups": warmups, "repeats": repeats,
              "environment": {"python": platform.python_version(), "platform": platform.system(),
                              "machine": platform.machine(), "processor": platform.processor(),
                              "versions": {p: importlib.metadata.version(p) for p in ("pydantic", "pytest", "jsonschema")},
                              "hash_seed": os.environ.get("PYTHONHASHSEED", "unset"), "model_loaded": False},
              "unavailable": {"M2": "NOT_RUN: no isolated index/model validated", "M3": "NOT_RUN: no authorization/model configured"}}
    config["manual_reviews_sha256"] = hashlib.sha256(manual_review_path.read_bytes()).hexdigest() if manual_review_path else None
    if annotations_v2:
        config["annotations_v2_sha256"] = hashlib.sha256(annotations_v2.read_bytes()).hexdigest()
        config["semantics_v2_code_sha256"] = hashlib.sha256(Path(__file__).with_name("semantics_v2.py").read_bytes()).hexdigest()
    if mode == "full_investigation":
        config["investigation_code_sha256"] = hashlib.sha256(Path(__file__).with_name("investigation.py").read_bytes()).hexdigest()
        config["full_path_isolation"] = "real route/summary/History reconstruction; injected memory sink, local KB, no RAG/vector export; no HTTP authentication test"
        config["timing_boundary"] = "warm full harness incl stage comparison, pristine cache copy, native orchestration/synthesis, memory serialization/reload; excludes HTTP/auth and operational PostgreSQL"
        config["grounding_code_sha256"] = hashlib.sha256(Path(__file__).with_name("grounding.py").read_bytes()).hexdigest()
    config["grounding_reviews_sha256"] = hashlib.sha256(grounding_reviews.read_bytes()).hexdigest() if grounding_reviews else None
    def execute_prediction(c):
        if mode == "full_investigation":
            from evaluation.analyzer.investigation import predict_full
            result = predict_full(c, payloads[c["case_id"]])
        else:
            result = predict(c, payloads[c["case_id"]], mode)
        if semantics:
            from evaluation.analyzer.semantics_v2 import project
            result["semantics_v2"] = project(result, payloads[c["case_id"]])
        return result
    predictions = []
    # Full adapter installs its own guard after Windows event-loop IPC setup.
    with (nullcontext() if mode == "full_investigation" else offline_guard()):
        for c in cases:
            samples = []
            try:
                for _ in range(warmups):
                    execute_prediction(c)
                result = None
                canonical = None
                for _ in range(repeats):
                    start = time.perf_counter()
                    result = execute_prediction(c)
                    samples.append(time.perf_counter() - start)
                    if canonical is not None and digest(result) != canonical:
                        raise ValueError("NONDETERMINISTIC_PREDICTION")
                    canonical = digest(result)
                result["prediction_sha256"] = canonical
                result["timing_seconds"] = samples
                predictions.append(result)
            except Exception as exc:
                predictions.append({"case_id": c["case_id"], "status": "ERROR", "error_type": type(exc).__name__,
                                    "error": str(exc), "timing_seconds": samples})
    reviewed = [c for c in cases if c["review_status"] == "REVIEWED"]
    reviewed_ids = {c["case_id"] for c in reviewed}
    manual = load_manual_reviews(manual_review_path, predictions)
    metrics, scores = score(reviewed, [p for p in predictions if p["case_id"] in reviewed_ids], manual)
    metrics["status"] = "REVIEWED_BASELINE" if reviewed else "INSUFFICIENT_DATA"
    draft = [c for c in cases if c["review_status"] == "DRAFT"]
    exploratory, draft_scores = score(draft, [p for p in predictions if p["case_id"] not in reviewed_ids], manual)
    metrics["exploratory_draft_only"] = {"status": "NOT_GOLD_NOT_ACCURACY_CERTIFICATION", **exploratory}
    metrics["composition"] = {"reviewed_executed": len(reviewed), "draft_executed": len(draft),
                              "heldout_executed": len(cases) if split == "heldout" else 0}
    if semantics:
        from evaluation.analyzer.semantics_v2 import score_semantics
        selected = [semantics[c["case_id"]] for c in cases]
        metrics["semantics_v2"] = {}
        for status in ("REVIEWED", "DRAFT"):
            cohort = [c for c in selected if c["review_status"] == status]
            ids = {c["case_id"] for c in cohort}
            metrics["semantics_v2"][status.lower()] = score_semantics(cohort, [p for p in predictions if p["case_id"] in ids])
        metrics["semantics_v2"]["status"] = "INSUFFICIENT_DATA" if not metrics["semantics_v2"]["reviewed"]["case_count"] else "REVIEWED_V2_BASELINE"
    queue = None
    if mode == "full_investigation":
        from evaluation.analyzer.grounding import review_queue, score_grounding, validate_reviews
        queue = review_queue(predictions)
        judgments = json.loads(grounding_reviews.read_text(encoding="utf-8")) if grounding_reviews else queue
        validate_reviews(judgments, predictions, payloads)
        metrics["grounding"] = score_grounding(judgments, predictions)
    output.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    write("config.json", config)
    write("metrics.json", metrics)
    write("manual_reviews.json", manual)
    if queue is not None:
        write("claim_grounding_queue.json", queue)
        write("grounding_metrics.json", metrics["grounding"])
    for name, values in (("predictions.jsonl", predictions), ("case_scores.jsonl", scores + draft_scores)):
        (output / name).write_text("".join(json.dumps(v, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n" for v in values), encoding="utf-8")
    with (output / "errors.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "error_type", "error"])
        writer.writeheader()
        writer.writerows({k: p[k] for k in writer.fieldnames} for p in predictions if p["status"] == "ERROR")
    return metrics
