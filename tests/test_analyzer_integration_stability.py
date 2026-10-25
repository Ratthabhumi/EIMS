"""Synthetic integration regressions; never use operational storage."""
from concurrent.futures import ThreadPoolExecutor

from evaluation.analyzer.investigation import predict_full
from tests.test_analyzer_investigation import source
from backend.domain.analyzer.services.event_knowledge import get_curated_summary
from backend.domain.analyzer.services.summary import _fallback_vendor_causes
from backend.domain.analyzer.services.bundle import build_evidence_items, validate_bundle
from backend.domain.analyzer.services.evidence import build_evidence_records
import pytest


def test_native_single_file_keeps_both_ctk_failure_coordinates():
    case, files = source('esxi_tracker')
    p = predict_full(case, files)
    refs = p['native_response']['solutionSummary']['evidenceItems']
    assert {x['lineNumber'] for x in refs} == {1, 2}
    assert p['isolated_history_roundtrip']


def test_unknown_vendor_cause_does_not_assert_failed_outcome():
    text = ' '.join(_fallback_vendor_causes('vmware', 'VMware', 'en')).lower()
    assert 'confirms' not in text and 'session/job failed' not in text


def test_parallel_curated_requests_are_independent_without_evaluator_reset():
    def request(i):
        value = get_curated_summary('4624', 'en')
        value.evidence.append(f'synthetic-only-{i}')
        return value
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(request, range(32)))
    for i, value in enumerate(results):
        assert [x for x in value.evidence if x.startswith('synthetic-only-')] == [f'synthetic-only-{i}']
    assert not any(x.startswith('synthetic-only-') for x in get_curated_summary('4624', 'en').evidence)


def test_context_is_bounded_original_and_never_crosses_compaction_gaps():
    rows = build_evidence_records([('safe.txt', 'benign\n2026-10-25T10:03:00Z Er(02) vmx - CTK_CTKUNLINK result:2620\n' + 'x'*700)])
    items = build_evidence_items([], records=rows)
    assert len(items) == 1
    item = items[0]
    assert item['lineNumber'] == 2 and item['sourceContext'][0]['text'] == 'benign'
    assert len(item['sourceContext'][-1]['text']) == 500 and item['sourceContext'][-1]['truncated']
    sparse = [r for r in rows if r.line_number != 1]
    assert all(x['lineNumber'] != 1 for x in build_evidence_items([], records=sparse)[0]['sourceContext'])
    assert build_evidence_items([], records=[]) == []


@pytest.mark.parametrize('names', [('same.txt', 'same.txt'), ('Same.TXT', 'same.txt'), ('a/same.txt', 'b/same.txt')])
def test_duplicate_normalized_filenames_cannot_overwrite_source_identity(names):
    with pytest.raises(ValueError, match='Duplicate source filenames'):
        validate_bundle([(name, b'synthetic-only') for name in names])


@pytest.mark.parametrize('action,message,expected', [
    ('add', 'Configuration error-log-retention=7 updated successfully', False),
    ('delete', 'Configuration error-log-retention=7 updated successfully', False),
    ('edit', 'Configuration update failed', True),
    ('edit', 'Configuration update failed but updated successfully', True),
    ('edit', 'Configuration error-log-retention=7 updated successfully', False),
])
def test_fortinet_controls_do_not_extend_success_suppression_without_evidence(action, message, expected):
    from backend.domain.analyzer.services.incident_extract import _is_successful_fortinet_configuration, _signal_strength
    line = f'logid="0100044547" devname="FG-SYNTHETIC" type="event" subtype="system" level="information" action="{action}" msg="{message}"'
    assert _is_successful_fortinet_configuration(line) == (action == 'edit' and 'failed' not in message)
    if expected:
        assert _signal_strength(line) >= 2


@pytest.mark.parametrize('text', ['', 'CTK_CTK', 'Info no failure', 'CTK_CTKUNLINK result:0'])
def test_empty_truncated_and_negative_controls_have_no_fabricated_source(text):
    assert build_evidence_items([], records=build_evidence_records([('synthetic.txt', text)])) == []


@pytest.mark.parametrize('text', ['password="SYNTHETIC_ONLY"', "pwd='SYNTHETIC_ONLY'", 'api_key=SYNTHETIC_ONLY',
                                 'access_token=SYNTHETIC_ONLY', 'Authorization: Bearer SYNTHETIC_ONLY',
                                 'Authorization: Basic SYNTHETIC_ONLY', '{"password":"SYNTHETIC_ONLY"}',
                                 r'{"password":"SYNTHETIC_ONLY\"TAIL"}'])
def test_credential_masking_preserves_line_boundaries_and_json_syntax(text):
    import json
    from backend.domain.analyzer.services.evidence_privacy import protect_log_text
    original = text + '\nbenign line\n'
    masked, policy = protect_log_text(original)
    assert 'SYNTHETIC_ONLY' not in masked and '[REDACTED]' in masked
    assert masked.count('\n') == original.count('\n') and policy['credentialsRedacted'] >= 1
    if text.startswith('{'):
        assert json.loads(masked.splitlines()[0])['password'] == '[REDACTED]'


def test_privacy_policy_preserves_forensic_identifiers_and_marks_controls(monkeypatch):
    from backend.domain.analyzer.services.evidence_privacy import protect_log_text, apply_context_policy
    from backend.domain.analyzer.schemas.analyze import EvidenceItem
    source = 'user=synthetic-user ip=192.0.2.4 path=/synthetic/private password policy failed\n'
    assert protect_log_text(source)[0] == source
    masked, policy = protect_log_text('line\x00one\nline\ttwo')
    assert masked == 'line\ufffdone\nline\ttwo' and policy['controlCharactersReplaced'] == 1
    monkeypatch.setenv('EIMS_EVIDENCE_CONTEXT', 'none')
    _, policy = protect_log_text(source)
    item = EvidenceItem(sourceFile='synthetic.txt', sourceContext=[{'lineNumber':1,'text':source}])
    apply_context_policy([item], {'synthetic.txt':policy})
    assert item.sourceContext == [] and item.sourceContextOrigin == 'withheld_by_policy'


@pytest.mark.parametrize('source', [
    '{"outer":{"password":"SYNTHETIC_SECRET"},"ip":"192.0.2.4"}',
    'url=https://example.invalid/?password=SYNTHETIC_SECRET&ip=192.0.2.4',
    'password="SYNTHETIC_SECRET\nSECOND_SECRET"\nip=192.0.2.4',
    'password="SYNTHETIC_SECRET\r\nSECOND_SECRET"\r\nip=192.0.2.4',
    'authorization: bAsIc SYNTHETIC_SECRET\nip=192.0.2.4',
    'password='+('SYNTHETIC_SECRET'*10000)+' ip=192.0.2.4',
], ids=['nested-json', 'query', 'multiline-lf', 'multiline-crlf', 'basic', 'long-line'])
def test_additional_credential_formats_preserve_correlation_and_line_coordinates(source):
    from backend.domain.analyzer.services.evidence_privacy import protect_log_text
    safe, policy = protect_log_text(source)
    assert 'SYNTHETIC_SECRET' not in safe and 'SECOND_SECRET' not in safe
    assert '192.0.2.4' in safe
    assert safe.count('\n') == source.count('\n')
    assert safe.count('\r') == source.count('\r')
    assert policy['policyVersion'] == 'credential_masking_v2'


def test_unknown_secret_formats_are_explicitly_outside_masking_contract():
    from backend.domain.analyzer.services.evidence_privacy import protect_log_text
    source = 'unknownopaque=SYNTHETIC_OPAQUE user=synthetic-user path=C:\\synthetic\\log ไทย'
    assert protect_log_text(source)[0] == source  # no full-DLP claim


@pytest.mark.parametrize('family', ['windows_event','fortinet','cisco_asa','linux_syslog','json','unknown_text','vmware','veeam_vbr'])
def test_limitations_follow_observed_evidence_not_vendor_defaults(family):
    from backend.domain.analyzer.services.incident_extract import extract_incident
    for text in ['2026-10-25T10:00:00Z service failed to connect', '2026-10-25T10:00:00Z operation completed successfully']:
        incident = extract_incident(text, family)
        narrative = ' '.join(incident['unknowns']+incident['nextEvidence']).lower()
        assert 'ctk' not in narrative and 'vmdk' not in narrative and 'locked' not in narrative
        if 'successfully' in text:
            assert incident['unknowns'] == []


def test_fortinet_success_summary_reports_activity_not_diagnostic_failure(monkeypatch):
    import asyncio
    from backend.domain.analyzer.services import summary
    monkeypatch.setattr(summary, '_translate', lambda text, target: text)
    text = 'devname="FG-LAB" logid="0100044547" type="event" subtype="system" level="information" action="edit" msg="Configuration setting error-log-retention=7 updated successfully"'
    result = asyncio.run(summary.build_summary('0100044547','Fortinet FortiGate','',[],language='en',
        source_family='fortinet',diagnostic_code='0100044547',evidence_text=text))
    assert 'configuration' in result.overview.lower() and '0100044547' in result.overview
    assert 'diagnostic' not in result.overview.lower()
    assert result.causes == []
    assert 'primary error' not in ' '.join(result.steps).lower()


def test_windows_1129_uses_observed_connectivity_not_generic_causes(monkeypatch):
    import asyncio
    from backend.domain.analyzer.services import summary
    monkeypatch.setattr(summary, '_translate', lambda text, target: text)
    result = asyncio.run(summary.build_summary('1129','Microsoft-Windows-GroupPolicy','',[],language='en',
        source_family='windows_event',evidence_text='Group Policy could not contact a domain controller; network connectivity failed.'))
    narrative = result.model_dump_json().lower()
    assert 'domain controller' in result.overview.lower()
    assert all(x not in narrative for x in ['process crashed','resource depletion','corrupted','restart','ctk'])
    assert 'unknown' in narrative


def test_ctk_failure_is_not_a_physical_cause_or_applicable_lock_kb():
    from backend.domain.analyzer.services.vendor_knowledge import get_vendor_summary, vendor_reference_results
    text = 'CTK_CTKUNLINK result:2620 Could not delete change tracking file'
    result = get_vendor_summary('VMWARE-CBT-DELETE-FAILED','en',text)
    assert 'unknown' in ' '.join(result.causes).lower()
    assert all(x not in ' '.join(result.causes).lower() for x in ['corrupt','missing','inconsisten','stale'])
    assert not any('418256' in r.link for r in vendor_reference_results('VMWARE-CBT-DELETE-FAILED',text,'en'))


def test_secure_websocket_rejects_before_registering_client(monkeypatch):
    import asyncio
    from backend.domain.telemetry import ws_controller
    monkeypatch.setattr(ws_controller.settings,'AUTH_MODE','secure')
    class Socket:
        closed=None
        async def close(self,code,reason): self.closed=code
        async def accept(self): raise AssertionError('Unauthenticated connection accepted')
    ws=Socket()
    asyncio.run(ws_controller.websocket_dashboard(ws,token='forged-query-token'))
    assert ws.closed==1008


@pytest.mark.parametrize('level,message', [('error','Configuration edit failed'),('error','Configuration edit updated successfully'),('information','Configuration edit failed but updated successfully')])
def test_contradictory_configuration_fields_do_not_claim_success(level,message):
    from backend.domain.analyzer.services.observed_summary import observed_event_summary
    text=f'logid="0100044547" devname="FG-LAB" type="event" subtype="system" level="{level}" action="edit" msg="{message}"'
    result=observed_event_summary('0100044547','FortiGate','fortinet',text,'en')
    assert 'not established' in result.overview
    assert 'no failure observed' not in result.overview


def test_windows_identity_does_not_invent_a_missing_connectivity_message():
    from backend.domain.analyzer.services.observed_summary import observed_event_summary
    result=observed_event_summary('1129','Microsoft-Windows-GroupPolicy','windows_event','Event ID: 1129','en')
    assert 'full event message' in result.overview
    assert 'reports failure' not in result.overview
    assert observed_event_summary('1129','Unrelated','windows_event','domain controller connectivity failed','en') is None


@pytest.mark.parametrize('outcome',['Success','Failed','Warning'])
def test_explicit_outcome_is_not_described_as_missing_after_ctk_failure(outcome):
    from backend.domain.analyzer.services.incident_extract import extract_incident
    text='2026-10-25T10:00:00Z CTK_CTKUNLINK result:2620\n'+f"2026-10-25T10:02:00Z Job session 'synthetic' has been completed, status: '{outcome}'"
    result=extract_incident(text,'veeam_vbr')
    assert not any('outcome is not present' in item for item in result['unknowns'])


def test_secure_mode_never_reads_or_publishes_unowned_history_vectors(monkeypatch):
    import asyncio
    from backend.domain.analyzer.services import vector_db
    monkeypatch.setattr(vector_db.settings, 'AUTH_MODE', 'secure')
    class ForbiddenDB:
        async def execute(self, *a, **kw):
            raise AssertionError('Shared vector store must not be touched')
    def forbidden(*a, **kw):
        raise AssertionError('No embedding/model for unowned private History')
    monkeypatch.setattr(vector_db, '_get_embedding', forbidden)
    async def check():
        assert await vector_db.search_similar_logs(ForbiddenDB(), 'synthetic-private', event_id='1129', source_family='windows_event') == []
        assert await vector_db.add_solution(ForbiddenDB(), '1129', 'synthetic-private', {'overview':'private'}) is None
    asyncio.run(check())


def test_analysis_search_subject_is_task_local_and_required():
    import asyncio
    from contextlib import asynccontextmanager
    from backend.domain.search.providers.analysis_provider import AnalysisSearchProvider, analysis_search_owner
    class DB:
        @asynccontextmanager
        async def begin_nested(self):
            yield
    class Provider(AnalysisSearchProvider):
        async def _search_vector(self, db, query, limit):
            before = analysis_search_owner.get()
            await asyncio.sleep(0)
            assert analysis_search_owner.get() == before
            return [before]
    async def request(name):
        token = analysis_search_owner.set(name)
        try:
            return await Provider().search(DB(), 'synthetic', 10)
        finally:
            analysis_search_owner.reset(token)
    async def check():
        assert await asyncio.gather(request('owner-A'), request('owner-B')) == [['owner-A'], ['owner-B']]
        assert analysis_search_owner.get() is None
        assert await Provider().search(DB(), 'synthetic', 10) == []
    asyncio.run(check())
