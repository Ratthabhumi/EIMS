"""Small deterministic Windows evidence gates, before optional synthesis.

Event identity describes the investigation context; it never establishes cause.
Only supplied lines are returned as evidence. No network or database access.
"""
from backend.domain.analyzer.schemas.analyze import SolutionSummary
import re


_SHUTDOWN_PROVIDERS = {
    '41': {'kernel-power', 'microsoft-windows-kernel-power'},
    '6008': {'eventlog'},
    '1074': {'user32', 'microsoft-windows-user32'},
    '1001': {'wer-systemerrorreporting', 'microsoft-windows-wer-systemerrorreporting'},
}


def _field(block, label):
    match = re.search(rf'^{label}\s*:\s*([^\r\n]+)', block, re.I | re.M)
    return match.group(1).strip() if match else ''


def _shutdown_context(event_id, provider, text, th):
    # Supported input: Event Viewer text blocks separated by blank lines or
    # the existing EVTX adapter's NEXT EVENT marker. Never pair global regexes
    # across different records or infer source from an Event ID alone.
    blocks = re.split(r'\r?\n\s*\r?\n(?:--- NEXT EVENT ---\s*)?', text or '')
    records = []
    for block in blocks[:40]:
        code = _field(block, r'Event\s*ID')
        source = _field(block, r'(?:Source|Provider(?:\s*Name)?)')
        if source.lower() in _SHUTDOWN_PROVIDERS.get(code, set()):
            records.append((code, block))
    if not records:
        # Direct summary callers may supply identity separately from message.
        # A structured block with an unrelated explicit source never falls back.
        has_identity = bool(re.search(r'^(?:Source|Provider|Event\s*ID)\s*:', text or '', re.I | re.M))
        if not has_identity and provider in _SHUTDOWN_PROVIDERS.get(event_id, set()):
            records = [(event_id, text or '')]
    if not records:
        return None
    codes = {code for code, _ in records}
    if '41' in codes or '6008' in codes:
        overview = ('พบหลักฐานการเริ่มระบบหลังปิดไม่สมบูรณ์ ต้องตรวจสาเหตุเพิ่มเติม' if th else
                    'Observed unexpected/unclean shutdown evidence; the root cause is not established.')
    elif '1074' in codes:
        overview = ('พบ User32 Event 1074: มีการร้องขอ shutdown/restart โปรดตรวจผู้เริ่มและเหตุผลที่ระบุ' if th else
                    'User32 Event 1074 reports an initiated shutdown/restart request; review the supplied initiator and reason.')
    else:
        overview = ('พบ WER Event 1001 โปรดตรวจข้อความ bugcheck ที่ให้มาและ crash dump' if th else
                    'WER Event 1001 observed; review the supplied bugcheck message and crash dump.')
    evidence = []
    for code, block in records[:8]:
        lines = [line.strip()[:500] for line in block.splitlines() if line.strip()]
        if lines:
            evidence.append(f'Event {code}: ' + ' | '.join(lines[:16]))
    limits = ([
        'Event 41 หรือ 6008 ไม่ยืนยันว่าไฟดับหรืออุปกรณ์จ่ายไฟเสีย',
        'แสดงตามลำดับข้อมูลนำเข้า ไม่ถือว่าเป็นลำดับเวลา ไม่ปรับ timezone หรือเติม timestamp ที่ขาด',
        'การปรากฏร่วมกันไม่ยืนยันว่าเป็นเหตุการณ์เดียวกันหรือมีความสัมพันธ์เชิงสาเหตุ',
    ] if th else [
        'Event 41 or 6008 does not prove a power outage or power-supply failure.',
        'Evidence retains input order, not a verified timeline. Timestamp/timezone strings are preserved; missing timestamps are not inferred.',
        'Co-occurrence does not establish the same incident, host or causal relationship.',
    ])
    if not evidence:
        limits.append('ยังไม่มีข้อความหลักฐานต้นฉบับที่เพียงพอ' if th else 'Relevant original event message evidence was not supplied.')
    steps = (['ตรวจ provider, ชื่อเครื่องและ timestamp ของแต่ละรายการ', 'เก็บเหตุการณ์ก่อนหน้าและ crash dump หากมี'] if th else
             ['Verify each provider, host and timestamp before relating records.', 'Collect preceding events and crash dumps if available; read bugcheck codes only from supplied evidence.'])
    return SolutionSummary(overview=overview, causes=[], steps=steps, evidence=evidence,
                           confidence='low' if evidence else 'undetermined', limitations=limits, nextEvidence=steps)


def windows_investigation(event_id: str, provider: str, text: str, language: str):
    provider = (provider or '').lower()
    shutdown = _shutdown_context(event_id, provider, text, language == 'th')
    if shutdown:
        return shutdown
    group_policy = event_id == '1129' and 'grouppolicy' in provider
    if not group_policy:
        return None
    th = language == 'th'
    terms = ('group policy', 'domain controller', 'connectivity')
    evidence = [line.strip()[:500] for line in (text or '').splitlines()
                if any(term in line.lower() for term in terms)][:8]
    overview = ('พบ Windows Group Policy Event 1129 โปรดตรวจข้อความเหตุการณ์และการเชื่อมต่อ domain controller'
                if th else 'Windows Group Policy Event 1129: review the event message and domain-controller connectivity.')
    limits = ['เหตุการณ์นี้ไม่ยืนยันสาเหตุด้าน DNS, เครือข่าย, สิทธิ์ หรือความเสียหายของระบบ'
              if th else 'This event does not establish a DNS, network, permission or system-corruption root cause.']
    next_evidence = (['เก็บรายละเอียดเหตุการณ์ Group Policy ที่เกี่ยวข้องและเวลาที่เกิด',
                      'ตรวจหลักฐาน DNS และการเข้าถึง domain controller ในช่วงเวลาเดียวกัน'] if th else
                     ['Collect related Group Policy event details and timestamps.',
                      'Check DNS and domain-controller reachability evidence for the same time window.'])
    if not evidence:
        limits.append('ยังไม่มีข้อความหลักฐานต้นฉบับที่เพียงพอ' if th else 'Relevant original event message evidence was not supplied.')
    return SolutionSummary(overview=overview, causes=[], steps=list(next_evidence),
                           evidence=evidence, confidence='low' if evidence else 'undetermined',
                           limitations=limits, nextEvidence=next_evidence)
