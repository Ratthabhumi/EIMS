import asyncio
from backend.domain.analyzer.services import summary
from backend.domain.analyzer.schemas.analyze import EventMetadata
from backend.domain.analyzer.services.operational_catalog import entry_for_metadata


def test_filtermanager_and_time_service_cannot_inherit_disk_knowledge():
    for provider, event in [('Microsoft-Windows-FilterManager', '11'), ('Microsoft-Windows-Time-Service', '129')]:
        meta = EventMetadata(provider=provider, eventId=event, sourceFamily='windows_event')
        assert entry_for_metadata(meta) is None
        result = asyncio.run(summary.build_summary(event, provider, '', [], language='en',
                            source_family='windows_event', evidence_text='Synthetic observed message'))
        assert result.causes == []
        assert 'Synthetic observed message' in result.overview
        assert 'disk' not in result.overview.lower()
        assert any('No verified provider-specific' in x for x in result.limitations)


def test_unknown_provider_never_gets_numeric_id_root_cause():
    result = asyncio.run(summary.build_summary('3005', 'APCPBEAgent', '', [], language='en',
                        source_family='windows_event', evidence_text='Synthetic device message'))
    assert result.causes == [] and result.confidence == 'limited'
    assert any('product/version' in x for x in result.steps)


def test_fortinet_configuration_fields_are_preserved_without_traffic_confusion():
    from backend.domain.analyzer.services.parser import parse_event_metadata
    text = ('logid="0100044546" type="event" subtype="system" level="information" '
            'cfgpath="firewall.policy" cfgobj="7" cfgattr="action[deny->accept]" '
            'cfgtid="123" user="synthetic-admin" ui="GUI" vd="root" tz="+0700"')
    meta = parse_event_metadata(text)
    assert meta.sourceFamily == 'fortinet'
    assert meta.diagnosticCode == '0100044546'
    assert meta.attributes['cfgpath'] == 'firewall.policy'
    assert meta.attributes['cfgtid'] == '123'
    assert meta.attributes['tz'] == '+0700'
