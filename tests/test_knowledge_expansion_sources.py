"""Knowledge expansion regression (hermetic): provenance is honest, nothing is promoted, identity isolation holds."""
from tests import catalog_expectations as X
import re

import pytest

from backend.domain.analyzer.services import operational_catalog as oc

CATALOG = oc.OPERATIONAL_CATALOG
WINDOWS = [e for e in CATALOG if e["source_family"] == "windows_event"]
SEC_PAGE = re.compile(r"^https://learn\.microsoft\.com/en-us/previous-versions/windows/it-pro/windows-10/security/"
                      r"threat-protection/auditing/event-(\d+)$")


def test_no_record_is_promoted_by_adding_sources():
    classes = {e["knowledge_class"] for e in CATALOG}
    assert classes == {"operational_context", "diagnostic_candidate"}
    assert {e["lifecycle_status"] for e in CATALOG} <= {"operational_context", "candidate"}
    summary = oc.knowledge_summary()["counts"]
    assert summary["source_verified"] == summary["validated"] == summary["approved"] == 0
    assert all(e["verification_status"] == "preserved_legacy" for e in WINDOWS)


def test_original_catalog_size_and_identities_are_preserved():
    ids = [e["catalog_id"] for e in CATALOG]
    assert len(ids) == len(set(ids)) == X.TOTAL  # exactly the two source files, no duplicates
    assert X.BASELINE_IDS <= set(ids)  # the 163-ID baseline is never lost
    assert len([e for e in CATALOG if e["source_family"] == "windows_event"]) == X.LEGACY_WINDOWS_COUNT


@pytest.mark.parametrize("entry", [e for e in WINDOWS if e["provider"] in ("Windows Security", "Windows Filtering Platform")
                                   and e["official_references"]], ids=lambda e: e["catalog_id"])
def test_audit_event_references_point_at_the_page_for_the_same_event_id(entry):
    refs = [r for r in entry["official_references"] if SEC_PAGE.match(r["url"])]
    if not refs:
        # Tranche 18: events documented only on an audit-subcategory page that lists the Event ID by name.
        assert len(entry["official_references"]) == 1
        r = entry["official_references"][0]
        assert r["url"].startswith("https://learn.microsoft.com/windows/security/threat-protection/auditing/audit-")
        assert f'"{entry["event_id"]}(' in r["scope"] and "human re-read pending" in r["scope"]
        return
    assert len(refs) == 1
    assert SEC_PAGE.match(refs[0]["url"]).group(1) == entry["event_id"]
    assert refs[0]["title"].startswith(entry["event_id"])
    assert "not claimed verified" in refs[0]["scope"]


def test_every_reference_is_https_with_scope_and_unreviewed_wording_is_never_claimed_verified():
    for entry in CATALOG:
        for ref in entry["official_references"]:
            assert ref["url"].startswith("https://") and ref["scope"].strip() and ref["title"].strip()
            if entry["knowledge_class"] == "operational_context":
                assert "verified" not in ref["scope"].lower() or "not claimed verified" in ref["scope"]


def test_candidate_guidance_always_states_its_evidence_and_never_invents_remediation():
    guided = [e for e in CATALOG if e["knowledge_class"] == "diagnostic_candidate" and e.get("diagnostic_guidance")]
    assert len(guided) >= 14
    for entry in guided:
        guidance = entry["diagnostic_guidance"]
        assert guidance["evidence_basis"]
        if not guidance.get("safe_remediation"):
            # definition-only sources: no remediation, rollback or verification may be fabricated
            assert all(v.startswith("Inference") for v in guidance.get("verification_criteria", []))  # labelled, never asserted
            assert not guidance.get("rollback") or guidance["rollback"].startswith("Not applicable")


def test_fortinet_taxonomy_reference_declares_the_version_gap():
    forti = [e for e in CATALOG if e.get("vendor") == "Fortinet"]
    assert len(forti) == 5
    for entry in forti:
        text = " ".join(r["scope"] for r in entry["official_references"] if "7.4.2" in r["title"])
        assert "6.2.14" in text and "does not establish applicability" in text
        assert "6.2.14" in entry["diagnostic_guidance"]["evidence_basis"]


def test_veeam_replica_guidance_is_scoped_to_the_replica_and_flags_data_loss():
    entry = next(e for e in CATALOG if e["diagnostic_code"] == "VEEAM-REPLICA-SNAPSHOT-CHAIN")
    guidance = entry["diagnostic_guidance"]
    assert "data loss" in guidance["risk"] and "production" in guidance["risk"]
    assert any("CDP" in f for f in guidance["expected_findings"])
    assert "inference" in guidance["evidence_basis"]
    assert entry["verification_status"] == "code_supported_with_contextual_reference"


def test_vmware_cbt_related_article_adds_no_remediation():
    for entry in (e for e in CATALOG if e["diagnostic_code"] == "VMWARE-CBT-DELETE-FAILED"):
        assert any("322285" in r["url"] for r in entry["official_references"])
        assert not entry.get("diagnostic_guidance")
        assert "no remediation is recorded" in entry["limitations"]


@pytest.mark.parametrize("event_id,provider,basis", [
    ("1001", "Microsoft-Windows-WER-SystemErrorReporting", "provider_and_id"),
    ("1001", "Windows Error Reporting", "provider_and_id"),
    ("1001", "SomethingElse", "provider_mismatch"),
    ("1001", "", "provider_ambiguous"),
    ("41", "Microsoft-Windows-Kernel-Power", None),
    ("4624", "Microsoft-Windows-Security-Auditing", "provider_and_id"),
    ("4624", "Disk", "provider_mismatch"),
    ("129", "Microsoft-Windows-Kernel-Power", "provider_unverified"),
])
def test_provider_identity_still_decides_which_record_matches(event_id, provider, basis):
    result = oc.resolve_windows_entry(event_id, provider)
    if basis is None:
        assert result["basis"] in {"provider_and_id", "provider_unverified"}
    else:
        assert result["basis"] == basis
    if result["basis"] in ("provider_mismatch", "provider_ambiguous"):
        assert result["kind"] == "none"
    if result["basis"] == "provider_unverified":
        assert result["kind"] == "contextual"   # a stated, unmatched provider is never a direct match


def test_unsupported_event_returns_no_false_match():
    assert oc.resolve_windows_entry("999999", "Microsoft-Windows-Security-Auditing")["basis"] == "no_record"


@pytest.mark.parametrize("event_id,symbol_or_phrase", [
    ("2001", "SIGNATURE_UPDATE_FAILED"), ("3002", "RTP_FEATURE_FAILURE"), ("5001", "RTP_DISABLED"),
    ("5010", "ANTISPYWARE_DISABLED"), ("5011", "ANTIVIRUS_ENABLED"), ("1150", "SERVICE_HEALTHY"),
])
def test_defender_records_follow_the_documented_event_meaning(event_id, symbol_or_phrase):
    """Regression for legacy wording that contradicted Microsoft's Defender event list (e.g. 2001 was 'updated successfully')."""
    entry = oc.resolve_windows_entry(event_id, "Microsoft-Windows-Windows Defender")["entry"]
    assert symbol_or_phrase in entry["description"]
    assert "Corrects earlier legacy wording" in entry["official_references"][0]["scope"]


def test_event_157_is_surprise_removal_not_a_successful_retry():
    entry = oc.resolve_windows_entry("157", "Disk")["entry"]
    assert "surprise removed" in entry["description"] and "retried and succeeded" not in entry["description"]


GAP_REFS = [
    ("Windows Application", "1000", "troubleshoot-application-service-crashing-behavior", "application crashing event"),
    ("Windows Application", "1001", "troubleshoot-application-service-crashing-behavior", "Windows Error Reporting"),
    ("Service Control Manager", "7000", "service-not-start-events-7000-7011-time-out-error", "timeout variant only"),
    ("Service Control Manager", "7011", "service-not-start-events-7000-7011-time-out-error", "slow-start services only"),
    ("Microsoft-Windows-FailoverClustering", "1069", "hyper-v-virtual-machine-input-migration-integration", "cluster resource failure"),
    ("PowerShell (Operational)", "4104", "about_logging_windows", "Does not define the catalog description"),
]


@pytest.mark.parametrize("provider,event_id,slug,phrase", GAP_REFS)
def test_gap_references_are_scoped_and_never_claim_verification(provider, event_id, slug, phrase):
    rec = next(e for e in WINDOWS if e["provider"] == provider and e["event_id"] == event_id
               and e["diagnostic_code"] == e.get("diagnostic_code", event_id) and "WER-System" not in e["diagnostic_code"])
    refs = [r for r in rec["official_references"] if slug in r["url"]]
    assert refs, (provider, event_id)
    assert all(r["url"].startswith("https://learn.microsoft.com/") and "human re-read pending" in r["scope"] for r in refs)
    assert any(phrase.lower() in r["scope"].lower() for r in refs)
    assert rec["verification_status"] == "preserved_legacy" and rec["knowledge_class"] == "operational_context"


def test_windows_reference_coverage_floor():
    assert sum(bool(e.get("official_references")) for e in WINDOWS) >= 92


from backend.domain.analyzer.services.parser import parse_event_metadata  # noqa: E402

NEW_ASA = [("411002", 4), ("411001", 4), ("105005", 1), ("106015", 6), ("106001", 2), ("106100", 6)]


@pytest.mark.parametrize("code,sev", NEW_ASA)
def test_new_asa_candidates_resolve_only_for_asa_through_the_real_parser(code, sev):
    for product in ("ASA", "FTD", "PIX"):
        meta = parse_event_metadata(f"%{product}-{sev}-{code}: Synthetic documented-message fixture")
        assert meta.eventId == code
        assert bool(oc.entry_for_metadata(meta)) == (product == "ASA")
    entry = oc.get_catalog_entry(code, "cisco_asa", "official_message_id")
    assert entry["knowledge_class"] == "diagnostic_candidate" and entry["lifecycle_status"] == "candidate"
    assert entry["verification_status"] == "official_documentation_verified"
    g = entry["diagnostic_guidance"]
    assert "human re-read pending" in g["evidence_basis"] and "no ASA software version" in g["evidence_basis"]
    assert g["rollback"].startswith("Not applicable") and g["verification_criteria"][0].startswith("Inference")


def test_asa_remediation_is_only_what_the_vendor_page_states():
    for code in ("411001", "106001", "106100"):  # vendor: none required -> no remediation recorded
        assert "safe_remediation" not in oc.get_catalog_entry(code, "cisco_asa")["diagnostic_guidance"]
    assert "check the physical line" in oc.get_catalog_entry("411002", "cisco_asa")["diagnostic_guidance"]["safe_remediation"][0]
    assert "trace the packets to the source" in oc.get_catalog_entry("106015", "cisco_asa")["diagnostic_guidance"]["safe_remediation"][0]


def test_scm_7011_guidance_is_vendor_scoped():
    rec = next(e for e in WINDOWS if e["provider"] == "Service Control Manager" and e["event_id"] == "7011")
    g = rec["diagnostic_guidance"]
    assert "ServicesPipeTimeout" in " ".join(g["safe_remediation"]) and "60000" in " ".join(g["safe_remediation"])
    assert "symptom of another problem" in g["risk"] and g["verification_criteria"][0].startswith("Inference")
    assert rec["verification_status"] == "preserved_legacy" and rec["knowledge_class"] == "operational_context"


def test_defender_1122_is_asr_audit_not_network_protection():
    rec = next(e for e in WINDOWS if e["provider"] == "Windows Defender" and e["event_id"] == "1122")
    assert "Audit Mode" in rec["title"] and "audit mode" in rec["description"]
    assert "network protection" not in " ".join(rec["keywords"]).lower()
    assert {"1121", "1129", "5007"} <= set(rec["related_events"])
    assert any("attack-surface-reduction-windows-events" in r["url"] for r in rec["official_references"])
    assert all("human re-read pending" in r["scope"] for r in rec["official_references"])


def test_wmi_activity_5857_5858_follow_microsoft_articles_and_do_not_overclaim():
    r57 = next(e for e in WINDOWS if e["provider"] == "Microsoft-Windows-WMI-Activity" and e["event_id"] == "5857")
    r58 = next(e for e in WINDOWS if e["provider"] == "Microsoft-Windows-WMI-Activity" and e["event_id"] == "5858")
    assert "provider started" in r57["description"] and "lateral movement" in r57["operator_context"] and "not by itself" in r57["operator_context"]
    assert "0x80041032" in r58["description"] and "many different ResultCode values" in r58["description"]
    assert "do not cover every 5858" in r58["operator_context"]
    assert all(r["scope"].endswith("human re-read pending.") for r in r57["official_references"] + r58["official_references"])


def test_windows_reference_coverage_floor_after_tranche_11():
    assert sum(bool(e.get("official_references")) for e in WINDOWS) >= 95


def test_scm_7045_and_bugcheck_1001_references_are_scoped_to_the_reboot_article():
    r7045 = next(e for e in WINDOWS if e["provider"] == "Service Control Manager" and e["event_id"] == "7045")
    r1001 = next(e for e in WINDOWS if e["event_id"] == "1001" and e["provider"] == "Microsoft-Windows-WER-SystemErrorReporting")
    for rec, phrase in ((r7045, "A service was installed in the system"), (r1001, "rebooted from a bugcheck")):
        refs = [r for r in rec["official_references"] if "troubleshoot-unexpected-reboots-system-event-logs" in r["url"]]
        assert refs and phrase in refs[0]["scope"] and refs[0]["scope"].endswith("human re-read pending.")
    assert "not as a security finding" in r7045["official_references"][0]["scope"]


def test_windows_reference_coverage_floor_after_tranche_14():
    assert sum(bool(e.get("official_references")) for e in WINDOWS) >= 97


def test_windows_update_20_and_vss_8193_references_do_not_overgeneralise():
    wu = next(e for e in WINDOWS if e["provider"] == "Microsoft-Windows-WindowsUpdateClient" and e["event_id"] == "20")
    vss = next(e for e in WINDOWS if e["provider"] == "VSS" and e["event_id"] == "8193")
    assert "not a full definition" in wu["official_references"][0]["scope"]
    scopes = " ".join(r["scope"] for r in vss["official_references"])
    assert "should not be considered a critical failure" in scopes and "has other causes" in scopes and "CoCreateInstance" in scopes
    for r in wu["official_references"] + vss["official_references"]:
        assert r["scope"].endswith("human re-read pending.") and r["url"].startswith("https://learn.microsoft.com/")


def test_windows_reference_coverage_floor_final():
    assert sum(bool(e.get("official_references")) for e in WINDOWS) >= 99
