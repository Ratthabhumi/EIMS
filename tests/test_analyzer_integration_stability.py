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
                                 'Authorization: Basic SYNTHETIC_ONLY', '{"password":"SYNTHETIC_ONLY"}'])
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
