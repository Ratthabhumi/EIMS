"""Versioned annotation roles; v1 truth and historical scores stay untouched."""
import json
import hashlib
import re

from evaluation.analyzer.runner import annotation_digest, digest
from evaluation.analyzer.scoring import classification, endpoint_correct, prf, ratio


def review_digest(case):
    return digest({k: v for k, v in case.items() if k not in {
        "review_status", "annotator_id", "reviewer_id", "reviewed_annotation_sha256"}})


def load_annotations(path, source_manifest, source_cases):
    import jsonschema
    doc = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(path.with_name("manifest.v2.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(doc)
    if not doc["cases"]:
        raise ValueError("v2 requires at least one explicitly annotated DEV case")
    if doc["source_manifest"] != source_manifest.name or doc["source_manifest_sha256"] != hashlib.sha256(source_manifest.read_bytes()).hexdigest():
        raise ValueError("v2 source manifest binding mismatch; explicit version migration required")
    base = {c["case_id"]: c for c in source_cases}
    found = {}
    for c in doc["cases"]:
        cid = c["case_id"]
        if cid in found or cid not in base or base[cid]["split"] != "dev":
            raise ValueError("v2 annotations must be unique existing DEV cases; heldout v1 lock is not replaced")
        if c["base_annotation_sha256"] != annotation_digest(base[cid]):
            raise ValueError("v2 annotation has stale v1 case binding")
        truth = c["truth"]
        allowed = {f["path"] for f in base[cid]["files"]}
        if truth["failure_present"] is False and any(truth[k] is not None for k in (
                "failure_type", "first_observed_failure", "last_observed_failure")):
            raise ValueError("nonfailure label contradicts failure fields")
        if truth["root_cause_status"] == "PROVEN" and not any(
                r["evidence_type"] == "ROOT_CAUSE" for r in truth["evidence_references"]):
            raise ValueError("proven root-cause proposal requires explicit root-cause evidence")
        refs = list(truth["evidence_references"])
        refs += [truth[k] for k in ("first_observed_failure", "last_observed_failure") if truth[k]]
        if truth["explicit_terminal_outcome"]:
            refs += truth["explicit_terminal_outcome"]["evidence"]
        for ref in refs:
            if ref["file"] not in allowed:
                raise ValueError("v2 evidence references unknown source")
            lines = (source_manifest.parent / ref["file"]).read_text(encoding="utf-8").splitlines()
            if not 1 <= ref["line"] <= ref.get("end_line", ref["line"]) <= len(lines):
                raise ValueError("v2 evidence span out of bounds")
        if c["review_status"] == "REVIEWED" and (
                not (c.get("reviewer_id") or "").strip() or c["reviewer_id"].strip().lower().startswith(("ai", "codex"))
                or c.get("reviewed_annotation_sha256") != review_digest(c)):
            raise ValueError("v2 review needs an actual human assertion bound to current labels")
        found[cid] = c
    return doc, found


def project(prediction, files):
    """Expose canonical existing signal ranks, not a new production detector.

    Legacy first/terminal includes warnings. v2 uses rank >=2 for failure,
    and never relabels the last technical signal as final job status.
    """
    from backend.domain.analyzer.services.evidence import build_evidence_records, order_records
    from backend.domain.analyzer.services.incident_extract import _is_noise, _signal_strength
    records = build_evidence_records([(n, text) for n, (_, text) in sorted(files.items())])
    failed = order_records([r for r in records if not _is_noise(r.raw_text) and _signal_strength(r.raw_text) >= 2])
    def ref(r):
        return {"file": r.source_file, "line": r.line_number} if r else None
    explicit = []
    # This is a role adapter for explicit status fields, not inferred outcomes.
    end = re.compile(r"(?:task|job)\s+session\b.*?has\s+been\s+completed\s*,?\s*status\s*:\s*['\"]?(failed|success|succeeded|warning)\b", re.I)
    for r in order_records(records):
        match = end.search(r.raw_text)
        if match:
            status = {"success": "SUCCEEDED", "succeeded": "SUCCEEDED", "failed": "FAILED", "warning": "WARNING"}[match.group(1).lower()]
            explicit.append({"status": status, "evidence": [ref(r)]})
    family = prediction["source_family"]
    primary = prediction.get("primary_file")
    metadata = prediction.get("per_file_metadata", {}).get(primary, {})
    identity = metadata.get("eventId") if family in {"windows_event", "fortinet", "cisco_asa", "json"} else None
    if identity in ("", "Unknown"):
        identity = None
    if family == "json" and primary in files:
        # The parser's JSON-LOG fallback/status label is not a source-provided
        # event identifier. Keep its raw metadata, but do not certify identity.
        raw = json.loads(files[primary][1])
        supplied = [str(raw[k]) for k in ("eventId", "event_id", "id", "code")
                    if isinstance(raw, dict) and k in raw and raw[k] is not None]
        if identity not in supplied:
            identity = None
    failure_type = metadata.get("diagnosticCode") or "UNCLASSIFIED_FAILURE" if failed else None
    return {"source_family": family, "event_identity": identity,
            "failure_present": bool(failed), "failure_type": failure_type,
            "first_observed_failure": ref(failed[0]) if failed else None,
            "last_observed_failure": ref(failed[-1]) if failed else None,
            "explicit_terminal_outcome": explicit[-1] if explicit else None,
            "root_cause_status": "UNKNOWN",
            "uncertainty_reason": "Existing signal ranks and explicit status only; possible causes are not proven root cause.",
            "legacy_signal_fields_preserved": True,
            "projection_policy": "existing _is_noise/_signal_strength >=2; last observed != explicit session outcome"}


def score_semantics(annotations, predictions):
    by_id = {p["case_id"]: p for p in predictions}
    n = len(annotations)
    tp = fp = fn = tn = 0
    event_pairs, failure_types, roots = [], [], []
    first = last = final = 0
    positive_terminal = positive_terminal_correct = failure_known = 0
    rows = []
    for c in annotations:
        t = c["truth"]
        p = by_id[c["case_id"]]
        failed = p["status"] == "ERROR"
        s = p.get("semantics_v2", {})
        expected = t["failure_present"]
        actual = s.get("failure_present")
        if expected is not None:
            failure_known += 1
            tp += expected is True and actual is True and not failed
            fp += expected is False and actual is True and not failed
            fn += expected is True and (actual is not True or failed)
            tn += expected is False and actual is False and not failed
        event_pairs.append((t["event_identity"] or "UNKNOWN", "ERROR" if failed else s.get("event_identity") or "UNKNOWN"))
        failure_types.append((t["failure_type"] or "NO_FAILURE", "ERROR" if failed else s.get("failure_type") or "NO_FAILURE"))
        roots.append((t["root_cause_status"], "ERROR" if failed else s.get("root_cause_status", "UNKNOWN")))
        def same_span(key):
            actual_ref = s.get(key)
            return not failed and endpoint_correct(t[key], [actual_ref] if actual_ref else [])
        f, l = same_span("first_observed_failure"), same_span("last_observed_failure")
        terminal_correct = not failed and t["explicit_terminal_outcome"] == s.get("explicit_terminal_outcome")
        first += f
        last += l
        final += terminal_correct
        positive_terminal += t["explicit_terminal_outcome"] is not None
        positive_terminal_correct += t["explicit_terminal_outcome"] is not None and terminal_correct
        rows.append({"case_id": c["case_id"], "event_identity_correct": event_pairs[-1][0] == event_pairs[-1][1],
                     "failure_detection_correct": expected is not None and not failed and expected == actual,
                     "first_correct": f, "last_correct": l, "explicit_terminal_correct": terminal_correct})
    return {"case_count": n, "event_identity": classification(event_pairs),
            "failure_detection": {**prf(tp, fp, fn, failure_known, "v2 binary observed failure; unknown truth excluded and counted"),
                                  "tn": tn, "known_truth": failure_known, "unknown_truth": n - failure_known,
                                  "accuracy": ratio(tp + tn, failure_known, n, "all known failure labels; case errors are incorrect"),
                                  "execution_errors": sum(p["status"] == "ERROR" for p in predictions)},
            "failure_type": classification(failure_types), "root_cause_status": classification(roots),
            "first_observed_failure": ratio(first, n, n, "exact file/line, explicit null accepted; no clock inference"),
            "last_observed_failure": ratio(last, n, n, "last canonical rank>=2 signal; not session completion"),
            "explicit_terminal_outcome": ratio(final, n, n, "exact explicit session status and reference, including null"),
            "positive_terminal_case_support": positive_terminal,
            "terminal_detection_sensitivity": ratio(positive_terminal_correct, positive_terminal, positive_terminal, "exact explicit status/reference on truth-positive terminal cases"),
            "root_cause_proof_precision": ratio(0, 0, 0, "NOT_MEASURED: requires reviewed causal-support judgments"),
            "rca_abstention_quality": ratio(0, 0, 0, "NOT_MEASURED: typed UNKNOWN projection does not prove native narrative abstention"),
            "case_scores": rows}
