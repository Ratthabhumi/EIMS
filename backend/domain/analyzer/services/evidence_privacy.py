"""Conservative credential masking before analysis, persistence or KB lookup.

Not a DLP classifier. Identifiers/paths are retained for investigation and owner
authorization. Line boundaries survive; transformed text is explicitly labelled.
"""
import os
import re

_CREDENTIAL = re.compile(
    r'''(?i)(\b(?:password|passwd|pwd|api[_-]?key|access[_-]?token|refresh[_-]?token|session[_-]?token|client[_-]?secret|secret|token)\b["']?\s*[:=]\s*)("(?:\\.|[^"\\\r\n])*"|'(?:\\.|[^'\\\r\n])*'|[^\s,;"']+)'''
)
_BEARER = re.compile(r'(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]+')
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def protect_log_text(text):
    def mask(match):
        value = match[2]
        quote = value[0] if value[0] in {'"', "'"} else ''
        return match[1] + quote + '[REDACTED]' + quote
    text, count = _CREDENTIAL.subn(mask, text or '')
    text, bearer = _BEARER.subn(lambda m: m[1] + '[REDACTED]', text)
    text, controls = _CONTROL.subn('\ufffd', text)
    return text, {'policyVersion':'credential_masking_v1', 'credentialsRedacted':count + bearer,
                  'controlCharactersReplaced':controls,
                  'contextRetention':'none' if os.environ.get('EIMS_EVIDENCE_CONTEXT') == 'none' else 'bounded'}


def apply_context_policy(items, policy_by_file):
    for item in items:
        policy = policy_by_file.get(item.sourceFile, {})
        if policy.get('contextRetention') == 'none':
            item.sourceContext = []
            item.sourceContextOrigin = 'withheld_by_policy'
        elif policy.get('credentialsRedacted') or policy.get('controlCharactersReplaced'):
            item.sourceContextOrigin = 'redacted_extracted_source_excerpt'
