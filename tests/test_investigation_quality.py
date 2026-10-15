"""Synthetic evidence-boundary regressions; no network or working database."""
import asyncio
import pytest
from backend.domain.analyzer.services import summary
from backend.domain.analyzer.services.incident_extract import extract_incident
from backend.domain.analyzer.schemas.analyze import SolutionSummary

GROUP_POLICY = 'The processing of Group Policy failed because of lack of network connectivity to a domain controller.'

@pytest.mark.parametrize('language',['en','th'])
def test_1129_reports_evidence_without_generic_causes(monkeypatch, language):
    monkeypatch.setattr(summary,'_translate',lambda value,*args:value)
    result=asyncio.run(summary.build_summary('1129','Microsoft-Windows-GroupPolicy','','',language,
        description=GROUP_POLICY,source_family='windows_event'))
    assert result.causes == []
    assert any('domain controller' in line for line in result.evidence)
    assert result.limitations and result.nextEvidence

@pytest.mark.parametrize('family',['unknown_text','windows_event','linux_syslog','fortinet','cisco_asa','palo_alto'])
def test_non_vmware_unknowns_do_not_inject_disk_hypotheses(family):
    result=extract_incident('2026-10-15T08:00:00Z Error: operation failed',family)
    unknowns=' '.join(result['unknowns']).lower()
    assert 'ctk' not in unknowns and 'vmdk' not in unknowns
    assert 'locked' not in unknowns and 'corrupt' not in unknowns

def test_41_does_not_diagnose_power_outage(monkeypatch):
    monkeypatch.setattr(summary,'_translate',lambda value,*args:value)
    result=asyncio.run(summary.build_summary('41','Microsoft-Windows-Kernel-Power','','','en',
        description='The system has rebooted without cleanly shutting down first.',source_family='windows_event'))
    assert result.causes == []
    assert 'does not prove a power outage' in ' '.join(result.limitations)

def test_deterministic_windows_gate_does_not_call_external_ai(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('evidence gate must be offline')
    monkeypatch.setattr(summary,'_build_from_gemini',forbidden)
    result=asyncio.run(summary.build_summary('1129','Microsoft-Windows-GroupPolicy','','','en',
        api_key='synthetic-test-key',description=GROUP_POLICY,source_family='windows_event'))
    assert result.causes == []

def test_legacy_solution_schema_remains_compatible():
    old=SolutionSummary.model_validate({'overview':'Saved historical analysis','causes':[],'steps':[],'confidence':'medium'})
    assert old.confidence=='medium'

def test_unknown_source_does_not_invite_external_vendor_hypotheses(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('unknown input must stay unidentified')
    monkeypatch.setattr(summary,'_build_from_gemini',forbidden)
    result=asyncio.run(summary.build_summary('Unknown','Unknown','','','en',
        api_key='synthetic-test-key',description='inventory note',source_family='unknown_text'))
    assert result.confidence==''
    assert not any('CTK' in line or 'VMDK' in line for line in result.causes)

def test_missing_windows_message_is_explicitly_undetermined():
    result=asyncio.run(summary.build_summary('1129','Microsoft-Windows-GroupPolicy','','','en',
        source_family='windows_event'))
    assert result.evidence==[] and result.confidence=='undetermined'

def test_unmatched_vendor_route_does_not_invent_medium_confidence(monkeypatch):
    from backend.api.routers.analyzer import analyze
    from backend.domain.analyzer.services import vector_db
    monkeypatch.setattr(analyze,'search_solutions',lambda *a,**kw:([],''))
    async def fake_summary(*a,**kw):return SolutionSummary(overview='Synthetic unknown vendor failure')
    async def no_export(*a,**kw):pass
    monkeypatch.setattr(analyze,'build_summary',fake_summary)
    monkeypatch.setattr(vector_db,'add_solution',no_export)
    class MemoryOnly:
        def add(self,row):self.row=row
        async def commit(self):pass
        async def refresh(self,row):row.id=1
    result=asyncio.run(analyze.submit_analysis(text='Veeam Backup & Replication: task session failed',
        file=None,language='en',db=MemoryOnly(),_user='synthetic',x_gemini_api_key=None))
    assert result.eventMetadata.sourceFamily=='veeam_vbr'
    assert result.solutionSummary.confidence==''

def test_generated_bootstrap_password_is_never_logged(monkeypatch):
    from backend.domain.analyzer import auth
    messages=[]
    monkeypatch.setattr(auth.settings,'ADMIN_PASSWORD',None)
    monkeypatch.setattr(auth.settings,'ENVIRONMENT','development')
    monkeypatch.delenv('ADMIN_PASSWORD',raising=False)
    monkeypatch.setattr(auth.logger,'warning',lambda text:messages.append(text))
    generated=auth._resolve_admin_password()
    assert generated and all(generated not in text for text in messages)
