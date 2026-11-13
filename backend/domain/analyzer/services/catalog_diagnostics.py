"""Evidence-qualified catalog context for network/Linux logs, without RCA claims."""
from backend.domain.analyzer.schemas.analyze import SearchResult, SolutionSummary
from backend.domain.analyzer.services.operational_catalog import entry_for_metadata
from backend.domain.analyzer.services.parser import parse_event_metadata


def matched_knowledge(source_family: str, text: str):
    if source_family not in ("fortinet", "cisco_asa", "palo_alto", "linux_syslog") or not text:
        return None, None
    meta = parse_event_metadata(text)
    if meta.sourceFamily != source_family:
        return None, None
    return meta, entry_for_metadata(meta)


def catalog_summary(source_family: str, text: str, language: str):
    meta, entry = matched_knowledge(source_family, text)
    if source_family not in ("fortinet", "cisco_asa", "palo_alto", "linux_syslog", "json"):
        return None
    th = language == "th"
    context = entry["description"] if entry else (
        "Parsed record has no matched diagnostic knowledge. Root cause remains unknown."
    )
    limitations = ["Static reference knowledge does not establish the cause or impact of this record."]
    if entry:
        limitations.append(entry["limitations"])
    return SolutionSummary(
        overview=("บริบทอ้างอิง (ยังไม่ยืนยันสาเหตุ): " if th else "Reference context (cause unconfirmed): ") + context,
        causes=["ยังไม่มีหลักฐานเพียงพอที่จะยืนยันสาเหตุ" if th else "No root cause is established by this record alone."],
        steps=(["ตรวจสอบข้อความต้นฉบับและลำดับเหตุการณ์ก่อนเปลี่ยนการตั้งค่า"] if th else
               list(entry["investigation_steps"]) if entry else ["Preserve the raw record and collect adjacent events."]),
        evidence=[meta.logName] if meta else [], confidence="limited", limitations=limitations,
        nextEvidence=["Collect same-device records and the relevant configuration for the observed time window."],
    )


def catalog_references(source_family: str, text: str):
    _, entry = matched_knowledge(source_family, text)
    if not entry:
        return []
    return [SearchResult(title=r["title"], link=r["url"], snippet=r["scope"], sourceType="official")
            for r in entry["official_references"]]
