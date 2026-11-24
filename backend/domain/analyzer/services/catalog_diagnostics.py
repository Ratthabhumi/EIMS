"""Evidence-qualified catalog context for network/Linux logs, without RCA claims."""
from backend.domain.analyzer.schemas.analyze import OperationalGuidance, SearchResult, SolutionSummary
from backend.domain.knowledge.catalog_adapter import operational_problems, operational_view
from backend.domain.knowledge.service import canonical_hash
from backend.domain.analyzer.services.operational_catalog import entry_for_metadata
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.vendor_diagnostics import candidate_for_fields, candidate_for_message, candidate_for_sqlstate
from backend.domain.analyzer.services.vendor_reference import reference_for_metadata


def _guidance(kind: str, record: dict) -> OperationalGuidance:
    view = operational_view(kind, record)
    state = record.get("review_status") or ("PENDING_HUMAN_REVIEW (legacy label: " + str(record.get("verification_status", "")) + ")" if kind == "legacy" else "")
    cid = record.get("catalog_id") or (f"candidate:{record['candidate_id']}" if kind == "candidate" else "")
    return OperationalGuidance(**view, reviewState=state, catalogId=cid, contentHash=canonical_hash(record) if cid else "", missing=operational_problems(view))


def guidance_for_entry(source_family: str, diagnostic_code: str):
    """Operational guidance for a legacy diagnostic served by the Veeam/VMware vendor adapter (not by catalog_summary)."""
    from backend.domain.analyzer.services.operational_catalog import get_catalog_entry
    entry = get_catalog_entry(diagnostic_code, source_family, "eims_diagnostic")
    return _guidance("legacy", entry) if entry else None


def matched_knowledge(source_family: str, text: str):
    if source_family not in ("fortinet", "cisco_asa", "palo_alto", "linux_syslog", "json") or not text:
        return None, None
    meta = parse_event_metadata(text)
    if meta.sourceFamily != source_family:
        return None, None
    return meta, entry_for_metadata(meta)


def catalog_summary(source_family: str, text: str, language: str):
    meta, entry = matched_knowledge(source_family, text)
    if source_family not in ("fortinet", "cisco_asa", "palo_alto", "linux_syslog", "json"):
        return None
    # Unmatched structured records should reach the generic no-failure policy;
    # catalog absence is not itself a diagnostic event.
    if entry is None and meta is not None and _field_candidate(meta):
        cand = _field_candidate(meta)
        return _message_summary(meta, cand, language, lead="Log fields documented by the vendor (not a diagnosis; cause unconfirmed): ")
    if entry is None:
        reference = reference_for_metadata(meta) if meta else None
        if reference:
            return _reference_summary(meta, reference, language)
        message_candidate = _message_candidate(meta)
        return _message_summary(meta, message_candidate, language) if message_candidate else None
    # An informational FortiGate accept is a policy decision, not a system failure.
    if (source_family == "fortinet" and str((meta.attributes or {}).get("action", "")).lower() == "accept"
            and str(meta.level or "").lower() in {"notice", "info", "information"}):
        return None
    th = language == "th"
    context = entry["description"] if entry else (
        "Parsed record has no matched diagnostic knowledge. Root cause remains unknown."
    )
    limitations = ["Static reference knowledge does not establish the cause or impact of this record."]
    if entry:
        limitations.append(entry["limitations"])
    base = SolutionSummary(
        overview=("บริบทอ้างอิง (ยังไม่ยืนยันสาเหตุ): " if th else "Reference context (cause unconfirmed): ") + context,
        causes=["ยังไม่มีหลักฐานเพียงพอที่จะยืนยันสาเหตุ" if th else "No root cause is established by this record alone."],
        steps=(["ตรวจสอบข้อความต้นฉบับและลำดับเหตุการณ์ก่อนเปลี่ยนการตั้งค่า"] if th else
               list(entry["investigation_steps"]) if entry else ["Preserve the raw record and collect adjacent events."]),
        evidence=[meta.logName] if meta else [], confidence="limited", limitations=limitations,
        nextEvidence=["Collect same-device records and the relevant configuration for the observed time window."],
    )
    field_cand = _field_candidate(meta) if meta else None
    if field_cand:
        return _enrich_with_candidate(base, field_cand)
    if entry:
        base.operationalGuidance = _guidance("legacy", entry)
    return base


def _field_candidate(meta):
    """Fortinet traffic log with documented field values (type/subtype/policyid/action) linked to a candidate."""
    if getattr(meta, "sourceFamily", "") != "fortinet":
        return None
    return candidate_for_fields(getattr(meta, "attributes", None) or {})


def _enrich_with_candidate(summary: SolutionSummary, cand: dict) -> SolutionSummary:
    """Append an unreviewed field-linked candidate to an existing summary without replacing its conclusions."""
    summary.causes = list(summary.causes) + ["Documented possibility, not established for this record: " + c for c in cand["likely_causes"]]
    summary.steps = list(summary.steps) + list(cand["diagnostic_steps"]) + ["Vendor-documented option (unreviewed): " + r for r in cand["remediation"]]
    summary.limitations = list(summary.limitations) + [
        "Linked diagnostic candidate " + cand["candidate_id"] + " (" + cand["version_scope"] + ") is unreviewed; its remediation and risk are as stated by the cited page.",
        "Documented risk: " + cand["operational_risk"], cand["limitations"]]
    summary.nextEvidence = list(summary.nextEvidence) + [c["command"] + " -> " + c["expected_evidence"] for c in cand["diagnostic_commands"]]
    summary.operationalGuidance = _guidance("candidate", cand)
    return summary


def _message_candidate(meta):
    attrs = (getattr(meta, "attributes", None) or {})
    if getattr(meta, "sourceFamily", "") == "linux_syslog" and attrs.get("codeType") == "documented_message":
        return candidate_for_message(attrs.get("messageKey", ""))
    return None


def _message_summary(meta, cand: dict, language: str, lead: str | None = None):
    """Summary for a server message quoted verbatim by the vendor documentation, via its linked diagnostic candidate."""
    th = language == "th"
    attrs = meta.attributes or {}
    seen = ", ".join(f"{k}={attrs[k]}" for k in ("database", "transactions", "seconds", "exitCode", "walFile") if attrs.get(k))
    return SolutionSummary(
        overview=("ข้อความที่เอกสารระบุตรงตัว (ไม่ใช่การวินิจฉัย สาเหตุยังไม่ยืนยัน): " if th else
                  (lead or "Message wording confirmed by the vendor documentation or upstream source (not a diagnosis; cause unconfirmed): ")) + cand["meaning"]
                 + (f" Observed: {seen}." if seen else ""),
        causes=["ยังไม่มีหลักฐานเพียงพอที่จะยืนยันสาเหตุ" if th else "No root cause is established by this record alone."]
               + ["Documented possibility, not established for this record: " + c for c in cand["likely_causes"]],
        steps=list(cand["diagnostic_steps"]) + ["Vendor-documented option (unreviewed): " + r for r in cand["remediation"]],
        evidence=[meta.logName] if meta else [], confidence="limited",
        limitations=["Linked diagnostic candidate " + cand["candidate_id"] + " (" + cand["version_scope"] + ") is unreviewed; its remediation and risk are as stated by the cited page.",
                     "Documented risk: " + cand["operational_risk"], cand["limitations"]],
        nextEvidence=[c["command"] + " -> " + c["expected_evidence"] for c in cand["diagnostic_commands"]],
        operationalGuidance=_guidance("candidate", cand),
    )


def _reference_summary(meta, reference: dict, language: str):
    """Definition-only context for a documented code, enriched by a linked diagnostic candidate when one exists.

    The candidate is unreviewed documentation (human re-read pending): its causes are possibilities, its remediation is
    what the vendor page states, and nothing is presented as the established cause of this record.
    """
    th = language == "th"
    desc = reference["description"]
    attrs = (getattr(meta, "attributes", None) or {})
    cand = candidate_for_sqlstate(attrs.get("sqlState", "")) if reference.get("product") == "PostgreSQL" else None
    overview = ("นิยามจากเอกสาร (ไม่ใช่การวินิจฉัย สาเหตุยังไม่ยืนยัน): " if th else "Documented definition (not a diagnosis; cause unconfirmed): ") + desc
    causes = ["ยังไม่มีหลักฐานเพียงพอที่จะยืนยันสาเหตุ" if th else "No root cause is established by this record alone."]
    steps = (["เก็บข้อความต้นฉบับและบันทึกของ unit เดียวกันก่อนและหลังเหตุการณ์"] if th else
             ["Preserve the raw record and the journal entries of the same unit before and after it."])
    limitations = ["Definition-only reference (source_referenced, human re-read pending); the source gives no diagnosis or remediation.",
                   reference["limitations"]]
    next_evidence = ["Collect the unit's earlier journal messages and its unit file / ExecStart settings for the same time window."]
    if cand:
        overview += " Linked diagnostic candidate (unreviewed documentation): " + cand["meaning"]
        causes += ["Documented possibility, not established for this record: " + c for c in cand["likely_causes"]]
        steps = list(cand["diagnostic_steps"]) + ["Vendor-documented option (unreviewed): " + r for r in cand["remediation"]]
        limitations = ["Linked diagnostic candidate " + cand["candidate_id"] + " (" + cand["version_scope"] + ") is unreviewed; its remediation and risk are as stated by the cited page.",
                       "Documented risk: " + cand["operational_risk"], cand["limitations"]] + limitations[:1]
        next_evidence = [c["command"] + " -> " + c["expected_evidence"] for c in cand["diagnostic_commands"]]
    return SolutionSummary(
        overview=overview, causes=causes, steps=steps,
        evidence=[meta.logName] if meta else [], confidence="limited", limitations=limitations, nextEvidence=next_evidence,
        operationalGuidance=_guidance("candidate", cand) if cand else None,
    )


def catalog_references(source_family: str, text: str):
    meta, entry = matched_knowledge(source_family, text)
    if not entry:
        reference = reference_for_metadata(meta) if meta else None
        if not reference:
            cand = (_message_candidate(meta) or _field_candidate(meta)) if meta else None
            return [SearchResult(title=s["title"], link=s["url"], snippet=cand["meaning"], sourceType="official")
                    for s in cand["official_sources"]] if cand else []
        src = reference["source"]
        return [SearchResult(title=src["title"], link=src["url"], snippet=reference["description"], sourceType="official")]
    return [SearchResult(title=r["title"], link=r["url"], snippet=r["scope"], sourceType="official")
            for r in entry["official_references"]]
