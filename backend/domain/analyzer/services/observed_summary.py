"""Narrow deterministic event semantics; no cause inferred from event ID alone."""
from backend.domain.analyzer.schemas.analyze import SolutionSummary
from backend.domain.analyzer.services.incident_extract import _is_successful_fortinet_configuration
from backend.domain.analyzer.services.parser import _fortinet_field, windows_group_policy_connectivity


def observed_event_summary(event_id, provider, family, text, language):
    th = language == 'th'
    lines = [line for line in text.splitlines() if line.strip()]
    config_event = family == 'fortinet' and lines and all(
        _fortinet_field(line,'logid') in {'0100044546','0100044547'} and
        _fortinet_field(line,'type').lower() == 'event' and
        _fortinet_field(line,'subtype').lower() == 'system' for line in lines)
    if config_event and not all(_is_successful_fortinet_configuration(line) for line in lines):
        return SolutionSummary(
            overview=(f'FortiGate configuration event {event_id}: ยังไม่ยืนยันการแก้ไขสำเร็จจากข้อมูลที่ให้มา' if th else
                      f'FortiGate configuration event {event_id}: a successful edit is not established by the supplied fields.'),
            causes=['สาเหตุและผลกระทบยังไม่ทราบ (UNKNOWN)' if th else 'Cause and operational impact remain UNKNOWN.'],
            steps=['ตรวจ level/action/msg ที่ขัดกันและเก็บ cfgpath/cfgattr พร้อม FortiOS version' if th else
                   'Inspect conflicting level/action/message fields and obtain cfgpath/cfgattr with the FortiOS version.'],
            limitations=['Event identity ไม่ยืนยันความสำเร็จหรือความล้มเหลวเพียงอย่างเดียว' if th else
                         'The event identity alone establishes neither success nor failure.'], confidence='low')
    if config_event:
        return SolutionSummary(
            overview=(f'FortiGate configuration event {event_id}: บันทึกการแก้ไขสำเร็จระดับ Information; ไม่พบความล้มเหลวในข้อความที่ให้มา' if th else
                      f'FortiGate configuration event {event_id}: successful informational edit; no failure observed in the supplied records.'),
            causes=[],
            steps=['ตรวจ cfgpath/cfgattr ผู้ดำเนินการ อุปกรณ์ และเวอร์ชัน FortiOS หากต้องตรวจสอบการเปลี่ยนแปลง' if th else
                   'For a configuration audit, obtain cfgpath/cfgattr, actor, original device context and FortiOS version.'],
            limitations=['ข้อมูลนี้ยังไม่ยืนยันรูปแบบ log สำหรับ FortiOS รุ่นใดหรือผลกระทบต่อการทำงาน' if th else
                         'The supplied fields do not validate a particular FortiOS format/version or the operational effect of the edit.'],
            confidence='medium')
    normalized_provider = provider.lower().replace('-', '').replace(' ', '')
    if family == 'windows_event' and event_id == '1129' and 'grouppolicy' in normalized_provider:
        connectivity = windows_group_policy_connectivity(event_id, provider, text)
        return SolutionSummary(
            overview=(('Group Policy ติดต่อ Domain Controller ไม่ได้ตามข้อความ Event 1129' if th else
                       'Group Policy Event 1129 reports failure to contact a Domain Controller.') if connectivity else
                      ('พบ Group Policy Event 1129 แต่ต้องอ่านข้อความเต็มก่อนสรุปอาการ' if th else
                       'Group Policy Event 1129 identified; the full event message is needed to establish the observed symptom.')),
            causes=['ยังไม่ทราบสาเหตุจริง (UNKNOWN); Event นี้ไม่ยืนยันว่า DNS, LDAP หรือเครือข่ายส่วนใดเป็นต้นเหตุ' if th else
                    'Actual root cause is UNKNOWN; this event does not establish which DNS, LDAP or network component caused the symptom.'],
            steps=['เก็บ System และ GroupPolicy Operational log พร้อม ActivityID และเวลาที่เกิดเหตุ' if th else
                   'Collect System and GroupPolicy Operational events with ActivityID and timestamps.',
                   'ตรวจ DNS/DC connectivity และข้อมูลเครือข่ายช่วงเดียวกันเพื่อแยกสมมติฐาน; ตรวจว่าตรงกับช่วง startup หรือไม่' if th else
                   'Check DNS/DC connectivity and contemporaneous network diagnostics to distinguish hypotheses; determine whether this occurred during startup.'],
            limitations=['ยังไม่ยืนยัน startup/network readiness หรือสาเหตุทางกายภาพ; ต้องมีหลักฐานเพิ่มก่อนแก้ configuration' if th else
                         'Transient startup/network readiness and physical causes are unconfirmed; obtain evidence before changing configuration.'],
            confidence='medium')
    return None
