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
