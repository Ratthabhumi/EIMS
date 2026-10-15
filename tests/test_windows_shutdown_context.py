"""Synthetic Event Viewer text blocks; provider-qualified, no services."""
import asyncio
import pytest
from backend.domain.analyzer.services.investigation import windows_investigation
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services import summary


def event(code, provider, message='', stamp='2026-10-15T01:00:00Z'):
    return f'Log Name: System\nSource: {provider}\nDate: {stamp}\nEvent ID: {code}\n{message}'


def check(text):
    meta = parse_event_metadata(text)
    return windows_investigation(meta.eventId, meta.provider, text, 'en')


def test_41_and_6008_are_observations_not_power_loss():
    result = check(event(41,'Microsoft-Windows-Kernel-Power','Unclean reboot')+'\n\n'+event(6008,'EventLog','Previous shutdown was unexpected'))
    assert '6008' in ' '.join(result.evidence)
    assert result.causes == [] and 'does not prove' in ' '.join(result.limitations)


def test_1074_reports_supplied_initiator_without_inventing_planned_reason():
    result = check(event(1074,'User32','The process synthetic-updater.exe initiated restart. Reason: Other (Unplanned)'))
    assert result is not None and result.causes == []
    assert 'synthetic-updater.exe' in ' '.join(result.evidence)
    assert 'initiated' in result.overview.lower()


def test_wer_bugcheck_code_comes_from_original_message():
    result = check(event(1001,'Microsoft-Windows-WER-SystemErrorReporting','Rebooted from a bugcheck. BugcheckCode: 0x0000009f'))
    assert result is not None and '0x0000009f' in ' '.join(result.evidence)
    assert result.causes == []


def test_missing_code_is_not_invented():
    result = check(event(41,'Microsoft-Windows-Kernel-Power','Unclean reboot'))
    assert '0x' not in ' '.join(result.evidence)


def test_input_order_and_timezone_strings_are_preserved():
    later='2026-10-15T09:00:00+07:00';earlier='2026-10-15T01:00:00Z'
    result=check(event(41,'Kernel-Power','Unclean reboot',later)+'\n\n'+event(6008,'EventLog','Unexpected shutdown',earlier))
    evidence='\n'.join(result.evidence)
    assert later in evidence and earlier in evidence
    assert evidence.index(later)<evidence.index(earlier)
    assert 'input order' in ' '.join(result.limitations).lower()


@pytest.mark.parametrize('code',[41,6008,1074,1001])
def test_same_ids_from_unrelated_providers_are_not_shutdown_evidence(code):
    assert check(event(code,'Synthetic-Unrelated-App','An unrelated record')) is None


def test_unrelated_6008_is_not_attached_to_real_41():
    result=check(event(41,'Kernel-Power','Unclean reboot')+'\n\n'+event(6008,'Synthetic-Unrelated-App','Do not mix providers'))
    assert 'Do not mix providers' not in ' '.join(result.evidence)


def test_missing_provider_is_not_guessed_from_event_id():
    meta=parse_event_metadata('Log Name: System\nEvent ID: 41\nUnclean restart')
    assert meta.provider == 'Unknown'
    assert windows_investigation(meta.eventId,meta.provider,'Unclean restart','en') is None


def test_missing_timestamp_has_no_assumed_timezone():
    result=check('Source: Kernel-Power\nEvent ID: 41\nUnclean restart')
    assert result is not None
    assert 'timestamp' in ' '.join(result.limitations).lower()
    assert '2026' not in ' '.join(result.evidence)


def test_1074_summary_is_offline(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('No synthesis for a qualified shutdown observation')
    monkeypatch.setattr(summary,'_build_from_gemini',forbidden)
    text=event(1074,'User32','A synthetic process initiated restart')
    result=asyncio.run(summary.build_summary('1074','User32','','','en',api_key='synthetic-test-key',description=text,source_family='windows_event'))
    assert result.causes == []


@pytest.mark.parametrize('code',['41','6008','1074','1001'])
def test_unqualified_shutdown_id_cannot_fall_through_to_curated_causes(code):
    result=asyncio.run(summary.build_summary(code,'Synthetic-Unrelated-App','','','en',
        description=event(code,'Synthetic-Unrelated-App','Unrelated record'),source_family='windows_event'))
    assert result.causes == []
    assert 'provider' in ' '.join(result.limitations).lower()
