"""Evaluation policy only. No Analyzer imports, model calls or I/O."""
from collections import Counter
import math


def ratio(numerator, denominator, case_support, policy):
    return {"value": numerator / denominator if denominator else None,
            "numerator": numerator, "denominator": denominator,
            "case_support": case_support, "policy": policy,
            "undefined": None if denominator else "EMPTY_DENOMINATOR"}


def prf(tp, fp, fn, support, policy):
    return {"precision": ratio(tp, tp + fp, support, policy),
            "recall": ratio(tp, tp + fn, support, policy),
            "f1": ratio(2 * tp, 2 * tp + fp + fn, support, policy),
            "tp": tp, "fp": fp, "fn": fn}


def classification(pairs):
    """Single-label exact classification; UNKNOWN is a class, errors are wrong."""
    classes = sorted({v for pair in pairs for v in pair})
    matrix = {t: {p: 0 for p in classes} for t in classes}
    for truth, prediction in pairs:
        matrix[truth][prediction] += 1
    per_class = {}
    for label in classes:
        tp = matrix[label][label]
        fp = sum(matrix[t][label] for t in classes if t != label)
        fn = sum(matrix[label][p] for p in classes if p != label)
        per_class[label] = prf(tp, fp, fn, sum(matrix[label].values()), "exact class; no exclusions")
    observed_classes = [c for c in classes if sum(matrix[c].values())]
    macro = {}
    for metric in ("precision", "recall", "f1"):
        values = [per_class[c][metric]["value"] for c in observed_classes]
        defined = [v for v in values if v is not None]
        macro[metric] = ratio(sum(defined), len(defined), len(pairs),
                              "mean over truth-supported classes with defined metric")
        macro[metric]["undefined_classes"] = [c for c in observed_classes if per_class[c][metric]["value"] is None]
    correct = sum(t == p for t, p in pairs)
    return {"accuracy": ratio(correct, len(pairs), len(pairs), "exact class incl UNKNOWN and ERROR"),
            "per_class": per_class, "confusion_matrix": matrix, "macro": macro,
            "micro": prf(correct, len(pairs) - correct, len(pairs) - correct,
                         len(pairs), "single-label micro over all classes")}


def spans(refs):
    return {(r["file"], n) for r in refs for n in range(r["line"], r.get("end_line", r["line"]) + 1)}


def endpoint_correct(expected, actual):
    if expected is None:
        return not actual
    return spans([expected]) == spans(actual)


def percentile(samples, q):
    if not samples:
        return None
    values = sorted(samples)
    index = (len(values) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)


def _norm_layer(value):
    if value is None or value == "":
        return None
    return str(value)


def _layer_pairs(cases, predictions, truth_key, pred_key):
    """Exact match for an optional semantic layer; only cases that declare the truth key are scored."""
    pairs, support = [], 0
    for c in cases:
        t = c["truth"]
        if truth_key not in t:
            continue
        support += 1
        p = predictions[c["case_id"]]
        failed = p.get("status") == "ERROR"
        truth_v = _norm_layer(t.get(truth_key))
        pred_v = None if failed else _norm_layer(p.get(pred_key))
        pairs.append((truth_v if truth_v is not None else "UNKNOWN",
                      "ERROR" if failed else (pred_v if pred_v is not None else "UNKNOWN")))
    return pairs, support


def _role_evidence(truth, key, legacy_fallback=False):
    if key in truth:
        return spans(truth.get(key) or [])
    if legacy_fallback:
        return spans(truth.get("evidence") or [])
    return set()


def score(cases, predictions, manual_reviews=None):
    """Caller selects REVIEWED vs DRAFT cohorts; never pool them here."""
    by_id = {p["case_id"]: p for p in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {c["case_id"] for c in cases}:
        raise ValueError("prediction/case identity mismatch")
    n = len(cases)
    source, diagnostic = [], []
    first = terminal = failures_fp = failures_tn_support = 0
    evidence_tp = evidence_fp = evidence_fn = citation_total = coordinate_ok = covered = relevant = 0
    file_ok = line_ok = 0
    id_tp = id_fp = id_fn = diag_ev_tp = diag_ev_fp = diag_ev_fn = 0
    id_relevant = id_covered = diag_relevant = diag_covered = 0
    info_cases = info_failure_penalties = 0
    corr = Counter(tp=0, fp=0, fn=0)
    kb_tp = kb_total = kb_expected = kb_covered = 0
    abst = Counter(tp=0, fp=0, fn=0)
    uncertain_count = false_certain = errors = 0
    vendor_errors = Counter()
    per_case = []
    for c in cases:
        p = by_id[c["case_id"]]
        t = c["truth"]
        failed = p.get("status") == "ERROR"
        errors += failed
        predicted_code = p.get("diagnostic_code") or "UNKNOWN"
        source.append((t["source_family"], "ERROR" if failed else p["source_family"]))
        diagnostic.append((t["diagnostic_code"] or "UNKNOWN", "ERROR" if failed else predicted_code))
        if diagnostic[-1][0] != diagnostic[-1][1]:
            vendor_errors[t["source_family"]] += 1
        f = endpoint_correct(t.get("first_failure"), p.get("first_failure", [])) and not failed
        z = endpoint_correct(t.get("terminal_failure"), p.get("terminal_failure", [])) and not failed
        first += f
        terminal += z
        expected = spans(t["evidence"])
        emitted = spans(p.get("evidence", []))
        evidence_tp += len(expected & emitted)
        evidence_fp += len(emitted - expected)
        evidence_fn += len(expected - emitted)
        identity_expected = _role_evidence(t, "identity_evidence")
        diagnostic_expected = _role_evidence(t, "diagnostic_evidence", legacy_fallback=("identity_evidence" not in t))
        identity_emitted = spans(p.get("identity_evidence", []))
        diagnostic_emitted = spans(p.get("diagnostic_evidence", p.get("evidence", [])))
        id_tp += len(identity_expected & identity_emitted)
        id_fp += len(identity_emitted - identity_expected)
        id_fn += len(identity_expected - identity_emitted)
        diag_ev_tp += len(diagnostic_expected & diagnostic_emitted)
        diag_ev_fp += len(diagnostic_emitted - diagnostic_expected)
        diag_ev_fn += len(diagnostic_expected - diagnostic_emitted)
        if identity_expected:
            id_relevant += 1
            id_covered += bool(identity_expected & identity_emitted)
        if diagnostic_expected:
            diag_relevant += 1
            diag_covered += bool(diagnostic_expected & diagnostic_emitted)
        informational = bool(t.get("informational_only"))
        if informational:
            info_cases += 1
        # Failure-oriented FP: empty diagnostic evidence expectation. Informational
        # identity citations and empty diagnostic expectations are not failure FPs.
        if not diagnostic_expected and "diagnostic_evidence" in t:
            failures_tn_support += 1
            if not informational:
                failures_fp += (bool(p.get("first_failure")) or bool(diagnostic_emitted)) and not failed
                info_failure_penalties += 0
            else:
                # Informational cases must not be penalized merely for lacking failure evidence.
                info_failure_penalties += 0
        elif not expected:
            failures_tn_support += 1
            if informational:
                failures_fp += 0
            else:
                failures_fp += bool(p.get("first_failure")) or bool(emitted)
        else:
            relevant += 1
            covered += bool(expected & emitted)
        # Count each emitted citation, including duplicates. Exact coordinates
        # are mechanical; semantic support requires a separate human judgment.
        for ref in p.get("evidence", []):
            citation_total += 1
            coordinate_ok += bool(ref.get("coordinate_valid"))
            file_ok += ref["file"] in {a for a, b in expected}
            line_ok += (ref["file"], ref["line"]) in expected
        pred_pairs = {tuple(sorted((a["a"], a["b"]))): a["related"] for a in p.get("correlation_pairs", [])}
        for pair in t["correlation_pairs"]:
            key = tuple(sorted((pair["a"], pair["b"])))
            got = pred_pairs.get(key, False)
            corr["tp"] += bool(pair["related"] and got)
            corr["fp"] += bool(not pair["related"] and got)
            corr["fn"] += bool(pair["related"] and not got)
        if p.get("kb_executed"):
            expected_kb, actual_kb = set(t["applicable_kb"]), set(p.get("kb", []))
            kb_tp += len(expected_kb & actual_kb)
            kb_total += len(actual_kb)
            kb_expected += len(expected_kb)
            kb_covered += len(expected_kb & actual_kb)
        should = t["abstain_expected"]
        did = p.get("identity_abstained", False) and not failed
        abst["tp"] += should and did
        abst["fp"] += not should and did
        abst["fn"] += should and not did
        uncertain_count += should
        false_certain += should and not did and not failed
        per_case.append({"case_id": c["case_id"], "status": p["status"],
                         "source_correct": source[-1][0] == source[-1][1],
                         "diagnostic_correct": diagnostic[-1][0] == diagnostic[-1][1],
                         "first_correct": bool(f), "terminal_correct": bool(z),
                         "extra_evidence": sorted(emitted - expected),
                         "missing_evidence": sorted(expected - emitted),
                         "informational_only": informational})
    event_pairs, event_support = _layer_pairs(cases, by_id, "event_identity", "event_identity")
    category_pairs, category_support = _layer_pairs(cases, by_id, "diagnostic_category", "diagnostic_category")
    outcome_pairs, outcome_support = _layer_pairs(cases, by_id, "outcome", "outcome")
    samples = [v for p in predictions for v in p.get("timing_seconds", [])]
    kb_support = sum(bool(p.get("kb_executed")) for p in predictions)
    manual = manual_reviews or {"claims": [], "citations": []}
    claims = [r for r in manual["claims"] if r["case_id"] in by_id and r["supported"] is not None]
    citations = [r for r in manual["citations"] if r["case_id"] in by_id and r["supported"] is not None]
    unsupported = ratio(sum(not r["supported"] for r in claims), len(claims),
                        len({r["case_id"] for r in claims}),
                        "human-reviewed material claims bound to prediction hash; uncertain labels excluded and counted")
    semantic = ratio(sum(r["supported"] for r in citations), len(citations),
                     len({r["case_id"] for r in citations}),
                     "human-reviewed citation support bound to prediction hash; coordinate validity alone insufficient")
    result = {
        "case_count": n, "error_count": errors, "source": classification(source),
        "diagnostic": classification(diagnostic), "diagnostic_errors_by_vendor": dict(vendor_errors),
        "event_identity": classification(event_pairs) if event_pairs else {
            "accuracy": ratio(0, 0, event_support, "optional layer; EMPTY when no annotated cases")},
        "diagnostic_category": classification(category_pairs) if category_pairs else {
            "accuracy": ratio(0, 0, category_support, "optional layer; EMPTY when no annotated cases")},
        "outcome": classification(outcome_pairs) if outcome_pairs else {
            "accuracy": ratio(0, 0, outcome_support, "optional layer; EMPTY when no annotated cases")},
        "first_failure_accuracy": ratio(first, n, n, "exact file/line-set; explicit null counts; errors wrong"),
        "terminal_failure_accuracy": ratio(terminal, n, n, "exact file/line-set; explicit null counts; errors wrong"),
        "evidence_span": prf(evidence_tp, evidence_fp, evidence_fn, n, "legacy combined evidence; prefer role metrics when annotated"),
        "identity_evidence_span": prf(id_tp, id_fp, id_fn, n, "identity/context citations only"),
        "diagnostic_evidence_span": prf(diag_ev_tp, diag_ev_fp, diag_ev_fn, n, "diagnostic/failure citations only"),
        "false_positive_failure_rate": ratio(failures_fp, failures_tn_support, failures_tn_support,
                                             "finding on truth-negative diagnostic cases; informational_only excluded from penalty"),
        "informational_only_cases": ratio(info_cases, n, n, "count of INFORMATIONAL_ONLY annotated cases"),
        "provenance": {
            "coordinate_validity": ratio(coordinate_ok, citation_total, n, "existing line and exact/truncated-prefix raw message; not semantic support"),
            "file_precision": ratio(file_ok, citation_total, n, "citation file in truth evidence"),
            "exact_line_precision": ratio(line_ok, citation_total, n, "citation file+line in truth evidence; repeated citations counted"),
            "citation_coverage": ratio(covered, relevant, relevant, "cases with at least one truth-supported emitted citation"),
            "identity_citation_coverage": ratio(id_covered, id_relevant, id_relevant, "identity evidence coverage"),
            "diagnostic_citation_coverage": ratio(diag_covered, diag_relevant, diag_relevant, "diagnostic evidence coverage"),
            "semantic_support_precision": semantic},
        "correlation": prf(corr["tp"], corr["fp"], corr["fn"],
                           sum(bool(c["truth"]["correlation_pairs"]) for c in cases),
                           "labeled unordered pairs; STRONG/MEDIUM association positive; WEAK not proven; never causation"),
        "kb": {"applicability_precision": ratio(kb_tp, kb_total, kb_support, "exact official URL against reviewed applicable_kb; prerequisites must be reviewed"),
               "recommendation_coverage": ratio(kb_covered, kb_expected, kb_support, "applicable URLs retrieved / annotated applicable URLs"),
               "prerequisite_satisfaction": ratio(0, 0, 0, "NOT_MEASURED; separate prerequisite review required"),
               "cross_vendor_contamination": ratio(0, 0, 0, "NOT_MEASURED; URL mismatch alone cannot establish vendor contamination")},
        "identity_abstention": prf(abst["tp"], abst["fp"], abst["fn"], n, "no diagnostic identity; NOT root-cause confidence or narrative abstention"),
        "false_certain_identity_rate": ratio(false_certain, uncertain_count, uncertain_count, "diagnostic identity emitted where UNKNOWN expected; errors separately counted"),
        "unsupported_claim_rate": unsupported,
        "manual_review": {"claim_labels": len(claims), "citation_labels": len(citations),
                          "uncertain_labels": sum(r["case_id"] in by_id and r["supported"] is None
                                                  for rows in manual.values() for r in rows),
                          "policy": "reviewed subset only; no claim of exhaustive narrative review"},
        "latency": {"p50_seconds": percentile(samples, .5), "p95_seconds": percentile(samples, .95),
                    "sample_count": len(samples), "raw_seconds": samples,
                    "policy": "perf_counter wall seconds; linear interpolated percentiles; no fabricated zeros"}}
    result["correlation"]["false_merge_count"] = corr["fp"]
    result["correlation"]["false_split_count"] = corr["fn"]
    return result, per_case
