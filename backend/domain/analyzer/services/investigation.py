"""Small deterministic Windows evidence gates, before optional synthesis.

Event identity describes the investigation context; it never establishes cause.
Only supplied lines are returned as evidence. No network or database access.
"""
from backend.domain.analyzer.schemas.analyze import SolutionSummary


def windows_investigation(event_id: str, provider: str, text: str, language: str):
    provider = (provider or '').lower()
    group_policy = event_id == '1129' and 'grouppolicy' in provider
    unexpected_restart = event_id == '41' and 'kernel-power' in provider
    if not (group_policy or unexpected_restart):
        return None
    th = language == 'th'
    terms = ('group policy', 'domain controller', 'connectivity') if group_policy else (
        'reboot', 'shutdown', 'shutting down', 'bugcheck', 'powerbutton')
    evidence = [line.strip()[:500] for line in (text or '').splitlines()
                if any(term in line.lower() for term in terms)][:8]
    if group_policy:
        overview = ('พบ Windows Group Policy Event 1129 โปรดตรวจข้อความเหตุการณ์และการเชื่อมต่อ domain controller'
                    if th else 'Windows Group Policy Event 1129: review the event message and domain-controller connectivity.')
        limits = ['เหตุการณ์นี้ไม่ยืนยันสาเหตุด้าน DNS, เครือข่าย, สิทธิ์ หรือความเสียหายของระบบ'
                  if th else 'This event does not establish a DNS, network, permission or system-corruption root cause.']
        next_evidence = (['เก็บรายละเอียดเหตุการณ์ Group Policy ที่เกี่ยวข้องและเวลาที่เกิด',
                          'ตรวจหลักฐาน DNS และการเข้าถึง domain controller ในช่วงเวลาเดียวกัน'] if th else
                         ['Collect related Group Policy event details and timestamps.',
                          'Check DNS and domain-controller reachability evidence for the same time window.'])
    else:
        overview = ('พบ Windows Kernel-Power Event 41: มีการเริ่มระบบหลังปิดไม่สมบูรณ์ ต้องตรวจหลักฐานเพิ่มเติม'
                    if th else 'Windows Kernel-Power Event 41 reports a restart after an unclean shutdown; further evidence is needed.')
        limits = ['Event 41 เพียงรายการเดียวไม่ยืนยันว่าไฟดับหรืออุปกรณ์จ่ายไฟเสีย'
                  if th else 'Event 41 alone does not prove a power outage or power-supply failure.']
        next_evidence = (['เก็บรายละเอียด BugcheckCode, เหตุการณ์ก่อนหน้า และ crash dump หากมี',
                          'เปรียบเทียบเวลา shutdown/restart กับบันทึกผู้ดูแลและแหล่งจ่ายไฟ'] if th else
                         ['Collect BugcheckCode details, preceding events and a crash dump if available.',
                          'Compare shutdown/restart timing with operator records and power-system evidence.'])
    if not evidence:
        limits.append('ยังไม่มีข้อความหลักฐานต้นฉบับที่เพียงพอ' if th else 'Relevant original event message evidence was not supplied.')
    return SolutionSummary(overview=overview, causes=[], steps=list(next_evidence),
                           evidence=evidence, confidence='low' if evidence else 'undetermined',
                           limitations=limits, nextEvidence=next_evidence)
