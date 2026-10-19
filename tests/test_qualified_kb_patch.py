import pytest
from backend.domain.analyzer.services.provider_knowledge import qualified_windows_summary, WINDOWS_PROFILES
from backend.domain.analyzer.services.catalog_diagnostics import catalog_summary
from backend.domain.analyzer.services.parser import parse_event_metadata


@pytest.mark.parametrize('event,provider,message', [
 ('8016','Microsoft-Windows-DNS-Client','Failed to register host A or AAAA resource records'),
 ('129','Microsoft-Windows-Time-Service','NtpClient unable to discover a domain peer'),
 ('11','Microsoft-Windows-FilterManager','File system filter does not support Bypass I/O'),
 ('1129','Microsoft-Windows-GroupPolicy','Group Policy failed due to network connectivity to a domain controller'),
 ('7031','Service Control Manager','The synthetic service terminated unexpectedly. Recovery action restart'),
 ('20','Microsoft-Windows-WindowsUpdateClient','Installation Failure: update Synthetic, error 0x80070002'),
 ('5719','NETLOGON','No domain controller is available'),
])
def test_positive_requires_provider_channel_and_message(event,provider,message):
    result = qualified_windows_summary(event,provider,message,'System','en')
    assert result.causes == [] and result.evidence[0] == message
    assert 'No verified provider-specific' not in ' '.join(result.limitations)
    for p,c,msg in [('WrongProvider','System',message),(provider,'Security',message),(provider,'System','unrelated message')]:
        negative = qualified_windows_summary(event,p,msg,c,'en')
        assert 'No verified provider-specific' in ' '.join(negative.limitations)


def test_apc_and_security_collection_boundaries():
    apc = qualified_windows_summary('3005','APCPBEAgent','Synthetic','Application','en')
    assert 'UNVERIFIED' in ' '.join(apc.limitations) and not apc.causes
    for code in ('4946','4947','4948','4950'):
        result = qualified_windows_summary(code,'Microsoft-Windows-Security-Auditing','rule setting changed','Security','en')
        assert 'not collected' in result.overview


@pytest.mark.parametrize('code',['0100044544','0100044545','0100044546','0100044547'])
@pytest.mark.parametrize('action',['Add','Edit','Delete'])
def test_fortinet_raw_ids_and_bounded_policy_actions(code,action):
    raw = f'logid="{code}" type="event" subtype="system" action="{action}" cfgpath="firewall.policy" cfgobj="7" cfgattr="dstintf[port1->port2]"'
    meta = parse_event_metadata(raw)
    assert meta.diagnosticCode == code and meta.attributes['logid'] == code
    result = catalog_summary('fortinet',raw,'en')
    assert 'Observed policy action: '+action.lower() in result.overview
    assert 'port1->port2' in result.overview
    assert 'actor authorization' in ' '.join(result.limitations)
    deny = parse_event_metadata(f'logid="{code}" type="traffic" subtype="forward" action="deny"')
    assert deny.diagnosticCode == 'traffic/forward'


def test_missing_fields_do_not_invent_policy_or_actor():
    raw='logid="0100044547" type="event" subtype="system"'
    result=catalog_summary('fortinet',raw,'en')
    assert 'Insufficient Evidence' in result.overview
    assert 'Observed policy action' not in result.overview
    other=catalog_summary('fortinet',raw+' cfgpath="system.global" action="Edit"','en')
    assert 'Observed policy action' not in other.overview
