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
    if cid == "win_policy":
        assert any(c["evidence_type"] == "SEVERITY" and c["evidence"][0]["line"] == 4 for c in a["claims"])
        assert any(c["evidence_type"] == "EVENT_IDENTITY" and c["evidence"][0]["line"] == 3 for c in a["claims"])
        assert all(c["category"] != "SUPPORTED_INFERENCE" for c in a["claims"])


@pytest.mark.parametrize('cid', ['esxi_tracker', 'win_policy', 'fort_config'])
def test_full_route_parity_against_isolated_fastapi_transport(monkeypatch, cid):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.routers.analyzer import analyze as api
    from backend.domain.analyzer.services import vector_db, summary
    from backend.domain.analyzer.services.vendor_knowledge import vendor_reference_results
    from evaluation.analyzer.investigation import MemoryHistory
    c, files = source(cid)
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


def test_json_fallback_label_is_not_source_provided_event_identity():
    c, files = source("json_info")
    with runner.offline_guard():
        prediction = runner.predict(c, files, "rule_only")
        projected = semantics_v2.project(prediction, files)
    assert prediction["per_file_metadata"][c["files"][0]["path"]]["eventId"] == "JSON-LOG"
    assert projected["event_identity"] is None


def test_literal_signature_maps_only_unique_exact_source_span():
    from evaluation.analyzer.investigation import make_claims
    response = {"eventMetadata": {"sourceFamily": "vmware"}, "solutionSummary": {
        "overview": "Synthetic overview", "evidence": ["Could not delete change tracking file"]}}
    line = "2026-10-25T00:00:00Z vmx: Could not delete change tracking file"
    files = {"a.txt": (line.encode(), line)}
    _, refs, missing = make_claims(response, files)
    assert not missing and len(refs) == 1
    r = refs[0]
    assert r["message"] == line and line[r["span_start"]:r["span_end"]] == r["quoted_excerpt"]
    _, refs, missing = make_claims(response, {**files, "b.txt": files["a.txt"]})
    assert not refs and missing[0]["reason"] == "SOURCE_LINE_AMBIGUOUS_OR_UNAVAILABLE"


@pytest.mark.parametrize("mutation", ['blank_reviewer','blank_rationale','padded_ai','category','remove_citation','alter_citation'])
def test_grounding_rejects_modified_proposal_and_empty_human_assertions(mutation):
    c, files=source('esxi_tracker')
    p=predict_full(c,files);p['prediction_sha256']=runner.digest(p)
    queue=grounding.review_queue([p])
    row=next(r for r in queue['judgments'] if r['evidence'])
    row.update(support_judgment='SUPPORTED',reviewer='human-fixture-only',rationale='Synthetic test only, never Gold')
    if mutation=='blank_reviewer': row['reviewer']='  '
    elif mutation=='blank_rationale': row['rationale']='  '
    elif mutation=='padded_ai': row['reviewer']='  AI-test'
    elif mutation=='category': row['claim_category']='HYPOTHESIS' if row['claim_category']!='HYPOTHESIS' else 'UNCERTAIN'
    elif mutation=='remove_citation': row['evidence']=[]
    else: row['evidence'][0]['line']=2 if row['evidence'][0]['line']==1 else 1
    with pytest.raises(ValueError):
        grounding.validate_reviews(queue,[p],{c['case_id']:files})


@pytest.mark.parametrize('reviewer', ['   ', '  AI-proposal', ' Codex-agent'])
@pytest.mark.parametrize('protocol', ['v1','v2'])
def test_annotation_review_receipts_reject_blank_or_disguised_ai(tmp_path, reviewer, protocol):
    from tests.test_analyzer_evaluation import copied_manifest
    manifest,doc=copied_manifest(tmp_path)
    c=next(c for c in doc['cases'] if c['case_id']=='esxi_tracker')
    if protocol=='v2':
        import hashlib
        v2=json.loads(V2.read_text(encoding='utf-8'))
        v2['source_manifest_sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest()
        row=next(x for x in v2['cases'] if x['case_id']=='esxi_tracker')
        row.update(review_status='REVIEWED',reviewer_id=reviewer,reviewed_annotation_sha256=semantics_v2.review_digest(row))
        path=manifest.parent/V2.name;path.write_text(json.dumps(v2),encoding='utf-8')
        with pytest.raises(ValueError,match='human assertion'):
            semantics_v2.load_annotations(path,manifest,doc['cases'])
        return
    c.update(review_status='REVIEWED',reviewer_id=reviewer,reviewed_annotation_sha256=runner.annotation_digest(c))
    manifest.write_text(json.dumps(doc),encoding='utf-8')
    with pytest.raises(ValueError,match='human reviewer'):
        runner.load_manifest(manifest)


def test_existing_review_pipeline_end_to_end_test_only(tmp_path, monkeypatch):
    """Artificial judgments exist only in tmp_path, never in the real Gold set."""
    from tests.test_analyzer_evaluation import copied_manifest
    original={p:p.read_bytes() for p in MANIFEST.parent.rglob('*') if p.is_file()}
    manifest,doc=copied_manifest(tmp_path)
    monkeypatch.setattr(runner,'REPO',tmp_path)
    monkeypatch.setattr(runner,'git',lambda *args:'fixture-sha')
    (tmp_path/'tests').mkdir()
    (tmp_path/'tests/test_analyzer_reliability.py').write_text('# synthetic review test only')
    c=next(c for c in doc['cases'] if c['case_id']=='esxi_tracker')
    # Human correction is simulated only to check preservation and receipt binding.
    c['truth']['notes']='Synthetic reviewer correction retained, not an actual Gold judgment'
    c.update(review_status='REVIEWED',reviewer_id='human-fixture-only',
             reviewed_annotation_sha256=runner.annotation_digest(c))
    manifest.write_text(json.dumps(doc),encoding='utf-8')
    out=tmp_path/'evaluation/analyzer/results/proposal'
    initial=runner.run(manifest,'full_investigation','dev',out,repeats=1,warmups=0)
    assert initial['composition']=={'reviewed_executed':1,'draft_executed':0,'heldout_executed':0}
    assert initial['source']['accuracy']['numerator']==1
    assert initial['source']['accuracy']['denominator']==1
    predictions=[json.loads(line) for line in (out/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    queue=grounding.review_queue(predictions)
    assert grounding.score_grounding(queue,predictions)['semantic_support_precision']['value'] is None
    judgments=deepcopy(queue);judgments['judgments']=judgments['judgments'][:3]
    for r,value in zip(judgments['judgments'],['SUPPORTED','UNSUPPORTED','UNCERTAIN']):
        r.update(support_judgment=value,reviewer='human-fixture-only',rationale='Artificial test-only semantic judgment; citation validity alone is insufficient')
    _,payloads=runner.load_manifest(manifest)
    grounding.validate_reviews(judgments,predictions,payloads)
    review=tmp_path/'judgments.json';review.write_text(json.dumps(judgments),encoding='utf-8')
    measured=runner.run(manifest,'full_investigation','dev',tmp_path/'evaluation/analyzer/results/reviewed',
                        repeats=1,warmups=0,grounding_reviews=review)
    g=measured['grounding']
    assert g['semantic_support_precision']['numerator']==1
    assert g['semantic_support_precision']['denominator']==2
    assert g['unsupported_claim_rate']['value']==0.5
    assert g['uncertain_judgments']==1
    assert g['review_coverage']['denominator']==len(predictions[0]['claims'])
    missing=deepcopy(judgments);missing['judgments'].pop(1)
    grounding.validate_reviews(missing,predictions,payloads)
    assert grounding.score_grounding(missing,predictions)['reviewed_binary_judgments']==1
    conflict=deepcopy(judgments);conflict['judgments'].append(deepcopy(conflict['judgments'][0]))
    conflict['judgments'][-1]['support_judgment']='UNSUPPORTED'
    with pytest.raises(ValueError,match='duplicate'):
        grounding.validate_reviews(conflict,predictions,payloads)
    stale=deepcopy(judgments);stale['judgments'][0]['prediction_sha256']='0'*64
    with pytest.raises(ValueError,match='stale'):
        grounding.validate_reviews(stale,predictions,payloads)
    unknown=deepcopy(judgments);unknown['judgments'][0]['claim_id']='nonexistent'
    with pytest.raises(ValueError,match='emitted claim'):
        grounding.validate_reviews(unknown,predictions,payloads)
    assert json.loads(manifest.read_text(encoding='utf-8'))['cases']==doc['cases']
    input_path=manifest.parent/c['files'][0]['path']
    input_path.write_text('altered synthetic input',encoding='utf-8')
    with pytest.raises(ValueError,match='SHA-256'):
        runner.load_manifest(manifest)
    assert all(p.read_bytes()==raw for p,raw in original.items())

@pytest.mark.parametrize('cid', ['bundle_related', 'esxi_heartbeat', 'bundle_unrelated', 'veeam_options', 'json_info', 'noise_filename', 'fort_accept', 'win_boot'])
def test_no_failure_recommendations_and_reopened_history(cid):
    c, files = source(cid)
    p = predict_full(c, files)
    summary = p['native_response']['solutionSummary']
    assert 'primary error line' not in ' '.join(summary['steps']).lower()
    assert 'no failure observed' in summary['overview'].lower()
    assert p['isolated_history_roundtrip']
    assert summary == p['reopened_isolated_history']['solutionSummary']
    assert p == predict_full(c, files)

@pytest.mark.parametrize('language', ['th', 'en'])
def test_informational_summary_ignores_unrelated_failure_snippets(language):
    import asyncio
    from backend.domain.analyzer.services.summary import build_summary
    with asyncio.Runner() as loop, runner.offline_guard():
        s = loop.run(build_summary('VMWARE-UNKNOWN', 'VMware',
            'Restart the server because the disk is corrupt.', [], language,
            source_family='vmware', evidence_text='2026-10-20T04:00:00Z info hostd: heartbeat idle'))
    assert ('ไม่พบความล้มเหลว' if language == 'th' else 'No failure observed') in s.overview
    assert s.causes == []
    assert not any('error' in step.lower() for step in s.steps)

@pytest.mark.parametrize('language', ['th', 'en'])
@pytest.mark.parametrize('text,code', [
    ('CTK_CTKUNLINK result:2620', 'VMWARE-CTK-2620'),
    ("Task session 'synthetic' has been completed, status: 'Failed'", 'VEEAM-SESSION-FAILED'),
])
def test_failure_investigation_not_suppressed(language, text, code):
    import asyncio
    from backend.domain.analyzer.services.summary import build_summary
    with asyncio.Runner() as loop, runner.offline_guard():
        s = loop.run(build_summary(code, 'VMware' if code.startswith('VMWARE') else 'Veeam', '', [], language,
            source_family='vmware' if code.startswith('VMWARE') else 'veeam_vbr', diagnostic_code=code, evidence_text=text))
    assert s.steps and s.causes
    assert 'No failure observed' not in s.overview
    assert 'ไม่พบความล้มเหลว' not in s.overview

@pytest.mark.parametrize('cid,field,expected', [
    ('win_policy', 'diagnosticCode', 'WINDOWS-GROUP-POLICY-CONNECTIVITY'),
    ('esxi_tracker', 'level', 'Error'),
])
def test_priority_canonical_metadata_regression(cid, field, expected):
    c, files = source(cid)
    result = predict_full(c, files)
    assert result['native_response']['eventMetadata'][field] == expected
    assert result['native_response']['eventMetadata'] == result['reopened_isolated_history']['eventMetadata']


def test_fortinet_observation_has_native_source_provenance():
    c, files = source('fort_config')
    result = predict_full(c, files)
    summary = result['native_response']['solutionSummary']
    assert len(summary['evidenceItems']) == 1
    item = summary['evidenceItems'][0]
    assert item['sourceFile'] == 'input.txt' and item['lineNumber'] == 1
    assert item['message'] == next(iter(files.values()))[1].strip()
    assert summary == result['reopened_isolated_history']['solutionSummary']
    overview = next(claim for claim in result['claims'] if claim['claim_id'] == 'overview')
    assert overview['evidence'] and overview['category'] == 'UNCERTAIN'
    assert all(not claim['evidence'] for claim in result['claims'] if claim['evidence_type'] in ('RECOMMENDATION', 'UNKNOWN'))

@pytest.mark.parametrize('event,provider,message,expected', [
 ('1129','Microsoft-Windows-GroupPolicy','Group Policy could not contact a domain controller; network connectivity failed.','WINDOWS-GROUP-POLICY-CONNECTIVITY'),
 ('1129','Unknown','Group Policy could not contact a domain controller.',None),
 ('1129','Microsoft-Windows-GroupPolicy','Additional details unavailable.',None),
 ('6005','EventLog','The Event Log service was started.',None),
 ('9999','OtherProvider','Operation failed.',None),
 ('1129','OtherGroupPolicyPlugin','Could not contact a domain controller.',None),
])
def test_windows_symptom_category_requires_identity_and_message(event, provider, message, expected):
    from backend.domain.analyzer.services.parser import parse_event_metadata
    text=f'Log Name: System\nSource: {provider}\nEvent ID: {event}\nLevel: Error\nDescription: {message}\n'
    assert parse_event_metadata(text).diagnosticCode == (expected or '')


def test_unrelated_1129_mention_is_not_a_windows_diagnosis():
    from backend.domain.analyzer.services.parser import parse_event_metadata
    assert not parse_event_metadata('An unrelated note mentions 1129 and GroupPolicy.').diagnosticCode


@pytest.mark.parametrize('prefix,level,critical', [('Er(02)','Error',True),('Wa(03)','Warning',False),('In(05)','Information',False)])
def test_vmware_record_prefix_severity(prefix,level,critical):
    from backend.domain.analyzer.services.vendor_parsers import parse_vmware
    from backend.domain.analyzer.services.incident_extract import extract_incident
    text=f'2026-10-20T06:08:11Z {prefix} vmx - heartbeat idle'
    m=parse_vmware(text, 'Er(02)-failure.log')
    assert (m.level,m.isCritical)==(level,critical)
    # A warning or level marker alone is not a proven technical failure.
    if level!='Error':
        assert not extract_incident(text,'vmware')['firstMeaningfulFailure']


def test_vmware_prefix_is_position_scoped_and_severity_is_maximum():
    from backend.domain.analyzer.services.vendor_parsers import parse_vmware,parse_veeam
    info='2026-10-20T06:08:11Z In(05) vmx - note contains Er(02) and Wa(03)'
    error='2026-10-20T06:08:12Z Er(02) vmx - synthetic operation'
    assert parse_vmware(info).level=='Information'
    assert parse_vmware('vmx - arbitrary text Er(02)').level=='Information'
    assert parse_vmware(info+'\n'+error).level==parse_vmware(error+'\n'+info).level=='Error'
    assert parse_veeam('RetryFailedJob=true').level=='Information'


def test_informational_citation_keeps_source_identity_without_failure_inference():
    from backend.domain.analyzer.services.evidence import build_evidence_records
    from backend.domain.analyzer.services.bundle import build_evidence_items
    _,files=source('fort_config'); text=next(iter(files.values()))[1]
    records=build_evidence_records([('config.txt',text),('other.txt','unrelated informational record')])
    items=build_evidence_items([],records=records)
    assert len(items)==1 and items[0]['sourceFile']=='config.txt'
    assert items[0]['sourceContext'][0]['text']==text.strip()
    assert build_evidence_items([],records=[])==[]
    assert build_evidence_items([],records=build_evidence_records([('config.txt',text.replace('action="edit"','action="unknown"'))]))==[]
