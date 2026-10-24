"""Isolated full-route parity, versioned roles and review-integrity checks."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from evaluation.analyzer import runner, semantics_v2, grounding
from evaluation.analyzer.investigation import predict_full

MANIFEST = runner.REPO / "evaluation/analyzer/gold/manifest.v1.json"
V2 = MANIFEST.with_name("manifest.v2.dev-draft.json")


def source(cid):
    doc, files = runner.load_manifest(MANIFEST)
    return next(c for c in doc["cases"] if c["case_id"] == cid), files[cid]


def test_v2_is_parallel_dev_only_and_preserves_v1_heldout():
    old = MANIFEST.read_bytes()
    lock = MANIFEST.with_name("heldout.v1.lock.json").read_bytes()
    doc, _ = runner.load_manifest(MANIFEST)
    _, v2 = semantics_v2.load_annotations(V2, MANIFEST, doc["cases"])
    assert len(v2) == 12 and all(c["review_status"] == "DRAFT" for c in v2.values())
    assert v2["fort_config"]["truth"]["event_identity"] == "0100044547"
    assert v2["fort_config"]["truth"]["failure_present"] is False
    assert v2["esxi_tracker"]["truth"]["last_observed_failure"]["line"] == 2
    assert v2["esxi_tracker"]["truth"]["explicit_terminal_outcome"] is None
    assert MANIFEST.read_bytes() == old and MANIFEST.with_name("heldout.v1.lock.json").read_bytes() == lock


def test_v2_rejects_contradictory_nonfailure_and_stale_base(tmp_path):
    import shutil
    doc, _ = runner.load_manifest(MANIFEST)
    shutil.copy(V2.with_name("manifest.v2.schema.json"), tmp_path)
    data = json.loads(V2.read_text())
    data["cases"][0]["base_annotation_sha256"] = "0" * 64
    path = tmp_path / V2.name
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="stale"):
        semantics_v2.load_annotations(path, MANIFEST, doc["cases"])
    data = json.loads(V2.read_text())
    c = next(c for c in data["cases"] if c["case_id"] == "fort_config")
    c["truth"]["failure_type"] = "invented_failure"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="contradicts"):
        semantics_v2.load_annotations(path, MANIFEST, doc["cases"])


def test_identity_is_not_failure_and_technical_error_not_job_outcome():
    for cid, event in (("win_boot", "6005"), ("fort_config", "0100044547")):
        c, files = source(cid)
        with runner.offline_guard():
            p = runner.predict(c, files, "rule_only")
            s = semantics_v2.project(p, files)
        assert s["event_identity"] == event and s["failure_present"] is False
        assert s["explicit_terminal_outcome"] is None
    c, files = source("esxi_tracker")
    with runner.offline_guard():
        s = semantics_v2.project(runner.predict(c, files, "rule_only"), files)
    assert s["failure_present"] and s["explicit_terminal_outcome"] is None
    assert s["root_cause_status"] == "UNKNOWN"


@pytest.mark.parametrize("status,expected", [("Failed", "FAILED"), ("Success", "SUCCEEDED"), ("Warning", "WARNING")])
def test_explicit_status_is_separate_from_last_failure(status, expected):
    c, files = source("veeam_tracker")
    name = c["files"][0]["path"]
    text = files[name][1] + f"[2026-10-20 04:01:09] Info [Veeam.Backup.Core] Task session 'synthetic-only' has been completed, status: '{status}'\n"
    files[name] = (text.encode(), text)
    with runner.offline_guard():
        p = runner.predict(c, files, "rule_only")
        s = semantics_v2.project(p, files)
    assert s["explicit_terminal_outcome"]["status"] == expected
    if expected != "FAILED":
        assert s["last_observed_failure"]["line"] == 2
        assert s["explicit_terminal_outcome"]["evidence"][0]["line"] == 3


@pytest.mark.parametrize("cid", ["win_policy", "esxi_tracker", "bundle_related", "noise_filename"])
def test_full_pipeline_really_runs_route_synthesis_and_memory_history(cid):
    c, files = source(cid)
    a = predict_full(c, files)
    b = predict_full(c, dict(reversed(list(files.items()))))
    assert a == b
    stages = [s["stage"] for s in a["investigation_trace"]]
    assert "production.build_summary" in stages
    assert "production.get_all_history" in stages
    assert a["isolated_history_roundtrip"] and a["history_sink_commits"] == 1
    assert a["native_response"]["solutionSummary"] == a["reopened_isolated_history"]["solutionSummary"]
    assert all(c["support_judgment"] == "NOT_REVIEWED" and c["reviewer"] is None for c in a["claims"])
    if cid == "esxi_tracker":
        assert any(s["stage"] == "deterministic_vendor_summary" and s["returned_summary"] for s in a["investigation_trace"])


def test_full_route_parity_against_isolated_fastapi_transport(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.routers.analyzer import analyze as api
    from backend.domain.analyzer.services import vector_db, summary
    from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
    from evaluation.analyzer.investigation import MemoryHistory
    c, files = source("esxi_tracker")
    expected = predict_full(c, files)["native_response"]
    sink = MemoryHistory()
    app = FastAPI()
    app.include_router(api.router, prefix="/analyze")
    # Overrides apply only to this newly-created in-process test application.
    # Production auth/settings are never changed; no live auth claim is made.
    app.dependency_overrides[api.get_db] = lambda: sink
    app.dependency_overrides[api.get_current_user] = lambda: "synthetic-evaluation"
    def local(event, provider, **kw):
        refs = vendor_reference_results(kw.get("diagnostic_code") or "", kw.get("evidence_text") or "", "en")
        return refs, "\n".join(r.snippet for r in refs)
    async def no_write(*a, **kw):
        return None
    async def no_rag(*a, **kw):
        return []
    monkeypatch.setattr(api, "search_solutions", local)
    monkeypatch.setattr(vector_db, "add_solution", no_write)
    monkeypatch.setattr(summary, "search_similar_logs", no_rag)
    with TestClient(app) as client:
        with runner.offline_guard():
            response = client.post("/analyze/", data={"language": "en"}, files={"file": ("input.txt", next(iter(files.values()))[0], "text/plain")})
    assert response.status_code == 200
    actual = response.json()
    for key in ("eventMetadata", "solutionSummary", "searchResults", "aiSummary"):
        assert actual[key] == expected[key]


def test_grounding_requires_real_claim_hash_coordinates_and_human_judgment():
    c, files = source("esxi_tracker")
    p = predict_full(c, files)
    p["prediction_sha256"] = runner.digest(p)
    queue = grounding.review_queue([p])
    grounding.validate_reviews(queue, [p], {c["case_id"]: files})
    m = grounding.score_grounding(queue, [p])
    assert m["semantic_support_precision"]["value"] is None
    assert m["unsupported_claim_rate"]["value"] is None
    assert m["review_coverage"]["value"] == 0
    assert m["status"] == "NOT_MEASURED"
    bad = deepcopy(queue)
    bad["judgments"][0]["support_judgment"] = "SUPPORTED"
    with pytest.raises(ValueError, match="actual reviewer"):
        grounding.validate_reviews(bad, [p], {c["case_id"]: files})
    bad = deepcopy(queue)
    bad["judgments"][0]["prediction_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="stale"):
        grounding.validate_reviews(bad, [p], {c["case_id"]: files})


def test_v2_empty_cohort_and_case_errors_do_not_score_as_abstention():
    assert semantics_v2.score_semantics([], [])["failure_detection"]["f1"]["value"] is None
    doc, _ = runner.load_manifest(MANIFEST)
    _, v2 = semantics_v2.load_annotations(V2, MANIFEST, doc["cases"])
    c = v2["veeam_tracker"]
    m = semantics_v2.score_semantics([c], [{"case_id": c["case_id"], "status": "ERROR"}])
    assert m["failure_detection"]["fn"] == 1
    assert m["event_identity"]["accuracy"]["numerator"] == 0
    assert m["root_cause_proof_precision"]["value"] is None


def test_source_inspector_bounds_escapes_and_reports_missing_history_source():
    from evaluation.analyzer.inspection import render, source_context
    files = {"sample.txt": (b"", "line one\n<script>alert('synthetic')</script>\nline three\n")}
    ref = {"file": "sample.txt", "line": 2}
    assert len(source_context(files, ref, radius=0)) == 1
    assert source_context({}, ref) is None
    with pytest.raises(ValueError):
        source_context(files, ref, radius=100)
    p = {"case_id": "synthetic-xss", "claims": [{"category": "UNCERTAIN", "evidence_type": "SEVERITY",
         "text": "<script>synthetic</script>", "evidence": [ref]}]}
    html = render(p, files)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "default-src 'none'" in html
    assert "Original source unavailable" in render(p, {})
    assert "not a PostgreSQL persistence" in html


def test_demo_has_explicit_outcome_without_claiming_causation():
    from tools.demo_analyzer_investigation import hero_inputs
    files = hero_inputs()
    c = {"case_id": "synthetic-demo-test-only", "files": [{"path": n} for n in files]}
    p = predict_full(c, files)
    s = semantics_v2.project(p, files)
    assert p["native_response"]["correlationConfidence"] == "medium"
    assert s["explicit_terminal_outcome"]["status"] == "FAILED"
    assert s["root_cause_status"] == "UNKNOWN"
    assert p["native_response"]["files"][0]["sourceFamily"] == "veeam_vbr"
    assert p["native_response"]["files"][1]["sourceFamily"] == "vmware"
