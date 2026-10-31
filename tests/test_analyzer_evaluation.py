"""Adversarial checks for evaluation integrity, not Analyzer fixture duplication."""
import hashlib
import json
import socket

import pytest

from evaluation.analyzer import runner
from evaluation.analyzer.scoring import classification, endpoint_correct, percentile, prf, ratio, score

MANIFEST = runner.REPO / "evaluation/analyzer/gold/manifest.v1.json"


def test_zero_denominators_never_become_success():
    assert ratio(0, 0, 0, "empty")["value"] is None
    assert prf(0, 0, 0, 0, "empty")["f1"]["value"] is None
    metrics, rows = score([], [])
    assert not rows
    assert metrics["unsupported_claim_rate"]["value"] is None
    assert metrics["source"]["accuracy"]["denominator"] == 0
    assert metrics["latency"]["p95_seconds"] is None


def test_confusion_macro_micro_with_unknown_and_errors():
    c = classification([("a", "a"), ("a", "UNKNOWN"), ("UNKNOWN", "a"), ("b", "ERROR")])
    assert c["accuracy"]["value"] == .25
    assert c["per_class"]["a"]["precision"]["value"] == .5
    assert c["per_class"]["a"]["recall"]["value"] == .5
    assert c["micro"]["f1"]["value"] == .25
    assert c["confusion_matrix"]["b"]["ERROR"] == 1


def test_latency_percentiles_do_not_invent_samples():
    assert percentile([], .95) is None
    assert percentile([9], .95) == 9
    assert percentile([0, 10], .95) == 9.5


def test_first_failure_requires_exact_file_and_span():
    expected = {"file": "a", "line": 2, "end_line": 3}
    assert endpoint_correct(expected, [{"file": "a", "line": 2}, {"file": "a", "line": 3}])
    assert not endpoint_correct(expected, [{"file": "b", "line": 2, "end_line": 3}])
    assert endpoint_correct(None, [])


def fixture():
    case = {"case_id": "x", "truth": {"source_family": "unknown_text", "diagnostic_code": None,
            "abstain_expected": True, "first_failure": None, "terminal_failure": None,
            "evidence": [], "correlation_pairs": [{"a": "a", "b": "b", "related": False}],
            "applicable_kb": []}}
    prediction = {"case_id": "x", "status": "OK", "source_family": "unknown_text",
                  "diagnostic_code": None, "identity_abstained": True,
                  "evidence": [{"file": "a", "line": 1, "coordinate_valid": True}],
                  "correlation_pairs": [{"a": "b", "b": "a", "related": True}]}
    return case, prediction


def test_valid_coordinates_are_not_semantic_support_and_false_merges_count():
    c, p = fixture()
    metrics, _ = score([c], [p])
    assert metrics["provenance"]["coordinate_validity"]["value"] == 1
    assert metrics["provenance"]["exact_line_precision"]["value"] == 0
    assert metrics["provenance"]["semantic_support_precision"]["value"] is None
    assert metrics["correlation"]["fp"] == 1
    assert metrics["identity_abstention"]["precision"]["value"] == 1
    assert metrics["false_positive_failure_rate"]["numerator"] == 1


def test_false_split_and_duplicate_citations_have_real_denominators():
    c, p = fixture()
    c["truth"]["correlation_pairs"][0]["related"] = True
    p["correlation_pairs"][0]["related"] = False
    c["truth"]["evidence"] = [{"file": "a", "line": 1}]
    p["evidence"] *= 2
    m, _ = score([c], [p])
    assert m["correlation"]["fn"] == 1
    assert m["provenance"]["exact_line_precision"]["denominator"] == 2
    assert m["evidence_span"]["tp"] == 1


def test_errors_cannot_be_scored_as_correct_abstention():
    c, _ = fixture()
    m, _ = score([c], [{"case_id": "x", "status": "ERROR"}])
    assert m["error_count"] == 1
    assert m["source"]["accuracy"]["numerator"] == 0
    assert m["identity_abstention"]["fn"] == 1


@pytest.mark.parametrize("name", ["../a", "/a", "C:/a", "D:/data", "a\\b", ""])
def test_traversal_and_drive_paths_fail_closed(tmp_path, name):
    with pytest.raises(ValueError):
        runner.safe_input(tmp_path, name)


def test_symlink_path_escape_is_rejected_when_host_supports_links(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic")
    try:
        (inside / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("Windows host refuses symlink creation")
    with pytest.raises(ValueError):
        runner.safe_input(inside, "link.txt")


def test_offline_guard_blocks_actual_socket_entrypoints():
    with runner.offline_guard(), pytest.raises(RuntimeError, match="NETWORK_DISABLED"):
        socket.create_connection(("example.invalid", 443))


def copied_manifest(tmp_path):
    import shutil
    target = tmp_path / "gold"
    shutil.copytree(MANIFEST.parent, target)
    path = target / MANIFEST.name
    doc = json.loads(path.read_text(encoding="utf-8"))
    # Tests own their review-state fixtures. Actual human review must not
    # break the suite or be silently downgraded in the real manifest.
    for c in doc["cases"]:
        c["review_status"] = "DRAFT"
        c.pop("reviewer_id", None)
        c.pop("reviewed_annotation_sha256", None)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path, doc


@pytest.mark.parametrize("mutation,error", [
    ("hash", "SHA-256"), ("group", "scenario-group"), ("review", "human reviewer"),
    ("frozen", "immutable lock"), ("span", "truth span"), ("duplicate_id", "duplicate case"),
    ("normalized", "duplicate-content"), ("pair", "invalid/duplicate truth pair"),
])
def test_manifest_integrity_failures(tmp_path, mutation, error):
    path, doc = copied_manifest(tmp_path)
    c = doc["cases"][0]
    h = next(c for c in doc["cases"] if c["split"] == "heldout")
    if mutation == "hash":
        c["files"][0]["sha256"] = "0" * 64
    elif mutation == "group":
        h["scenario_group"] = c["scenario_group"]
    elif mutation == "review":
        c["review_status"] = "REVIEWED"
    elif mutation == "frozen":
        h["truth"]["abstain_expected"] = not h["truth"]["abstain_expected"]
    elif mutation == "span":
        c["truth"]["evidence"][0]["line"] = 999
    elif mutation == "duplicate_id":
        doc["cases"][1]["case_id"] = c["case_id"]
    elif mutation == "normalized":
        text = (path.parent / c["files"][0]["path"]).read_text()
        f = h["files"][0]
        raw = text.upper().encode()
        (path.parent / f["path"]).write_bytes(raw)
        f["sha256"] = hashlib.sha256(raw).hexdigest()
    elif mutation == "pair":
        b = next(c for c in doc["cases"] if c["case_id"] == "bundle_related")
        b["truth"]["correlation_pairs"][0]["b"] = "missing.txt"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        runner.load_manifest(path)


def test_corpus_is_nonempty_draft_and_heldout_is_locked():
    doc, payloads = runner.load_manifest(MANIFEST)
    assert len(doc["cases"]) == len(payloads) == 17
    assert all(c["review_status"] in {"DRAFT", "REVIEWED"} for c in doc["cases"])
    assert sum(c["split"] == "heldout" for c in doc["cases"]) == 5


def test_draft_heldout_and_unavailable_modes_never_execute(tmp_path):
    with pytest.raises(ValueError, match="heldout execution"):
        runner.run(MANIFEST, "rule_only", "heldout", tmp_path / "out", include_draft=True)
    with pytest.raises(ValueError, match="NOT_RUN"):
        runner.run(MANIFEST, "rag", "dev", tmp_path / "out")


def test_actual_prediction_order_invariance_and_mode_trace():
    doc, inputs = runner.load_manifest(MANIFEST)
    c = next(c for c in doc["cases"] if c["case_id"] == "bundle_related")
    files = inputs[c["case_id"]]
    with runner.offline_guard():
        a = runner.predict(c, files, "rule_only")
        b = runner.predict(c, dict(reversed(list(files.items()))), "rule_only")
        kb = runner.predict(c, files, "rule_kb")
    assert a == b
    assert not a["kb_executed"] and kb["kb_executed"]
    assert a["source_family"] == kb["source_family"]
    assert "vendor_reference_results" not in {s["stage"] for s in a["trace"]}
    assert "vendor_reference_results" in {s["stage"] for s in kb["trace"]}


def test_duplicate_predictions_rejected():
    c, p = fixture()
    with pytest.raises(ValueError, match="identity"):
        score([c], [p, p])


def test_stale_human_review_receipt_rejected(tmp_path):
    path, doc = copied_manifest(tmp_path)
    c = doc["cases"][0]
    c.update(review_status="REVIEWED", reviewer_id="human-fixture-only",
             reviewed_annotation_sha256=runner.annotation_digest(c))
    c["truth"]["notes"] = "edited after review"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt"):
        runner.load_manifest(path)


def test_manual_claim_and_citation_labels_are_counted_not_keywords(tmp_path):
    c, prediction = fixture()
    prediction["prediction_sha256"] = "a" * 64
    prediction["incident"] = {"first": "failure label without proven cause"}
    row = {"case_id": "x", "prediction_sha256": "a" * 64, "item_id": "c1",
           "text": "failure label without proven cause", "supported": False,
           "reviewer_id": "human-fixture-only", "rationale": "synthetic review fixture"}
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"claims": [row], "citations": []}))
    manual = runner.load_manual_reviews(path, [prediction])
    m, _ = score([c], [prediction], manual)
    assert m["unsupported_claim_rate"]["numerator"] == 1
    assert m["unsupported_claim_rate"]["denominator"] == 1
    row["prediction_sha256"] = "b" * 64
    path.write_text(json.dumps({"claims": [row], "citations": []}))
    with pytest.raises(ValueError, match="stale"):
        runner.load_manual_reviews(path, [prediction])


def test_predict_does_not_import_operational_database_vector_or_http(monkeypatch):
    import builtins
    original = builtins.__import__
    forbidden = ("backend.api", "backend.core.database", "backend.domain.analyzer.services.vector_db", "sqlalchemy")
    def guarded(name, *args, **kwargs):
        if any(name.startswith(prefix) for prefix in forbidden):
            pytest.fail("operational component reached: " + name)
        return original(name, *args, **kwargs)
    doc, payloads = runner.load_manifest(MANIFEST)
    c = doc["cases"][0]
    monkeypatch.setattr(builtins, "__import__", guarded)
    with runner.offline_guard():
        assert runner.predict(c, payloads[c["case_id"]], "rule_kb")["status"] == "OK"


def test_runner_keeps_drafts_out_of_reviewed_metrics_and_preserves_output(tmp_path, monkeypatch):
    manifest, _ = copied_manifest(tmp_path)
    monkeypatch.setattr(runner, "REPO", tmp_path)
    monkeypatch.setattr(runner, "git", lambda *args: "fixture-sha")
    # Schema and input validation still use the actual nonempty corpus;
    # only the output workspace and Git metadata are synthetic here.
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_analyzer_reliability.py").write_text("# no copied fixtures")
    output = tmp_path / "evaluation/analyzer/results/run"
    result = runner.run(manifest, "rule_only", "dev", output, include_draft=True, repeats=1, warmups=0)
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["source"]["accuracy"]["value"] is None
    assert result["exploratory_draft_only"]["source"]["accuracy"]["denominator"] == 12
    before = (output / "metrics.json").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        runner.run(manifest, "rule_only", "dev", output, include_draft=True)
    assert before == (output / "metrics.json").read_bytes()


def test_case_exception_is_recorded_and_included_in_denominator(tmp_path, monkeypatch):
    manifest, _ = copied_manifest(tmp_path)
    monkeypatch.setattr(runner, "REPO", tmp_path)
    monkeypatch.setattr(runner, "git", lambda *args: "fixture-sha")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_analyzer_reliability.py").write_text("# synthetic")
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(runner, "predict", fail)
    output = tmp_path / "test-results/run"
    m = runner.run(manifest, "rule_only", "dev", output, include_draft=True, repeats=1, warmups=0)
    assert m["exploratory_draft_only"]["error_count"] == 12
    assert m["exploratory_draft_only"]["source"]["accuracy"]["denominator"] == 12
    assert len((output / "errors.csv").read_text().splitlines()) == 13


@pytest.mark.parametrize('field,value',[('reviewer_id','  '),('reviewer_id',' AI-proposal'),('rationale','  ')])
def test_legacy_manual_review_requires_nonblank_human_assertion(tmp_path,field,value):
    _,prediction=fixture()
    prediction.update(prediction_sha256='a'*64,incident={'first':'synthetic failure'})
    row={'case_id':'x','prediction_sha256':'a'*64,'item_id':'c1','text':'synthetic failure',
         'supported':False,'reviewer_id':'human-fixture-only','rationale':'Artificial test only'}
    row[field]=value
    path=tmp_path/'review.json';path.write_text(json.dumps({'claims':[row],'citations':[]}),encoding='utf-8')
    with pytest.raises(ValueError,match='human reviewer'):
        runner.load_manual_reviews(path,[prediction])
