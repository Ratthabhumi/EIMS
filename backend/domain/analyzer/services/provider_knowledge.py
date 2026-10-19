"""Provider-qualified, message-grounded Windows fallback; no numeric-ID RCA."""
import re
import json
from pathlib import Path
from backend.domain.analyzer.schemas.analyze import SolutionSummary


def normalized_provider(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower()).removeprefix('microsoftwindows')


CHECKS = {
    ('grouppolicy', '1129'): 'Check domain-controller connectivity and the original Group Policy processing message.',
    ('dnsclient', '8016'): 'Check the original DNS error code, adapter and DNS registration context.',
    ('timeservice', '129'): 'Check the original NTP peer discovery message and configured time source.',
    ('filtermanager', '11'): 'Check the named file-system filter, volume and operation in the original message.',
    ('servicecontrolmanager', '7031'): 'Identify the named service, termination details and adjacent Application events.',
    ('apcpbeagent', '3005'): 'Confirm the APC product/version and consult its matching vendor documentation.',
    ('windowsupdateclient', '20'): 'Record the update identity and HRESULT before checking matching update guidance.',
    ('netlogon', '5719'): 'Check the domain-controller discovery message and network readiness at the event time.',
}

WINDOWS_PROFILES = json.loads(Path(__file__).with_name('windows_provider_knowledge.json').read_text('utf-8'))


def qualified_windows_summary(event_id, provider, message, channel, language):
    profiles = [p for p in WINDOWS_PROFILES if p['event_id'] == str(event_id)]
    if not profiles:
        return None
    entry = next((p for p in profiles if p['provider'] == normalized_provider(provider)), None)
    fallback = provider_fallback(event_id, provider, message, language)
    fallback.evidence = [message[:600]] if message else []
    if not message:
        fallback.confidence = 'undetermined'
    if not entry or channel.casefold() != entry['channel'].casefold() or not re.search(entry['message_pattern'], message):
        if entry and entry['provider'] == 'apcpbeagent':
            fallback.limitations.append(entry['meaning'])
        fallback.limitations.append('Channel and matching message are required before applying a provider-specific definition.')
        return fallback
    fallback.overview = entry['meaning'] + ' Observed: ' + message[:600]
    fallback.limitations = [entry['scope'], 'Reference context does not establish the root cause. Original timestamps and raw evidence are retained separately.']
    fallback.evidence = [message[:600], entry['reference']]
    return fallback


def provider_fallback(event_id, provider, message, language):
    """Unknown definitions stay unverified; supplied original text is evidence."""
    th = language == 'th'
    check = CHECKS.get((normalized_provider(provider), str(event_id)),
                       'Verify the provider, channel and original message against documentation for this product/version.')
    observed = str(message or '').strip()[:600]
    return SolutionSummary(
        overview=('ข้อความที่สังเกตได้: ' if th else 'Observed message: ') +
                 (observed or ('ไม่มีข้อความเหตุการณ์ต้นฉบับ' if th else 'Original event message unavailable.')),
        causes=[], steps=[check], confidence='limited',
        limitations=['No verified provider-specific knowledge available. Numeric Event ID alone does not establish meaning or root cause.'],
        nextEvidence=['Preserve provider, channel, event timestamp, record ID and full original message.'],
    )
