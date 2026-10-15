"""Knowledge-base quality policy, enforced as tests.

Policy (lightweight, student-maintainable):
1. Identity: operational event_ids unique; vendor diagnostic_codes unique.
2. Completeness: vendor entries carry signatures, references, limitations,
   investigation steps and scope; operational entries carry provider,
   description and related events.
3. Honesty: entry 41 names several possible causes (never power loss alone);
   1129 stays provider-qualified to GroupPolicy.
4. References: `official_references` hosts must be vendor-owned
   documentation, the Fortinet doc CDN, or pinned upstream source code.
   Anything else fails closed.
5. Status vocabulary: verification_status / support_level use only the
   known labels (no silent "verified" inflation).

Audit snapshot (15 Oct 2026, representative sample):
- 41/6008/1129: qualified wording, GroupPolicy-qualified provider — PASS.
- VEEAM-REPLICA-SNAPSHOT-CHAIN: evidence-conditioned, limitations explicit,
  next-evidence present, status code_supported_with_contextual_reference.
- Fortinet x5 refs via fortinetweb S3 CDN (docs.fortinet.com attachments):
  genuine vendor-published content — ALLOWED with explicit rule.
- AUTH-FAIL cites openssh-portable auth.c on master: authoritative source
  code but a moving target — ALLOWED as source reference, version pinning
  recommended (recorded, not silently marked documentation).
"""

import urllib.parse

from backend.domain.analyzer.services.operational_catalog import get_catalog

# Vendor-owned documentation hosts (official references only).
OFFICIAL_HOSTS = {
    "learn.microsoft.com",
    "support.microsoft.com",
    "docs.microsoft.com",
    "helpcenter.veeam.com",
    "www.veeam.com",
    "veeam.com",
    "support.broadcom.com",
    "broadcom.com",
    "kb.vmware.com",
    "knowledge.broadcom.com",
    "www.cisco.com",
    "cisco.com",
    "docs.fortinet.com",
    "fortinet.com",
    "docs.paloaltonetworks.com",
}

# Non-documentation but legitimate source hosts (allowed with a note).
SOURCE_HOSTS = {
    # Fortinet documentation CDN (docs.fortinet.com attachments).
    "fortinetweb.s3.amazonaws.com",
    # Upstream OpenSSH source for auth-logging format facts.
    "github.com",
}


def _ref_urls(entry):
    refs = entry.get("official_references") or []
    out = []
    for r in refs:
        out.append(r.get("url") if isinstance(r, dict) else r)
    return [u for u in out if u]


def _host(url):
    try:
        return urllib.parse.urlparse(str(url)).netloc.lower()
    except Exception:
        return ""


VENDOR_STATUSES = {
    "code_supported",
    "code_supported_with_contextual_reference",
    "official_documentation_verified",
}


def _vendor_entries(catalog):
    return [e for e in catalog if e.get("verification_status") in VENDOR_STATUSES]


def _operational_entries(catalog):
    return [e for e in catalog if e.get("verification_status") == "preserved_legacy"]


def test_catalog_size_and_identity_uniqueness():
    catalog = get_catalog()
    assert len(catalog) == 163
    op = _operational_entries(catalog)
    vendor = _vendor_entries(catalog)
    assert len(op) == 141
    assert len(vendor) == 22
    op_ids = [str(e.get("event_id")) for e in op]
    assert len(set(op_ids)) == len(op_ids), "duplicate operational event_id"
    # Identity is composite (family, code_type, code): the same VMware
    # signature is legitimately reachable from both veeam_vbr and vmware.
    identities = [
        (str(e.get("source_family")), str(e.get("code_type")),
         str(e.get("diagnostic_code")))
        for e in vendor
    ]
    assert len(set(identities)) == len(identities), "duplicate vendor identity"


def test_vendor_entry_completeness():
    for e in _vendor_entries(get_catalog()):
        code = e.get("diagnostic_code")
        assert e.get("source_family"), code
        assert e.get("product"), code
        assert e.get("observed_signatures"), code
        assert e.get("limitations"), code
        assert e.get("investigation_steps"), code
        assert e.get("verification_status"), code
        assert e.get("support_level"), code
        assert e.get("compatibility_scope"), code
        refs = e.get("official_references") or []
        if not refs:
            # Empty URL references are allowed ONLY as an explicitly
            # documented gap: limited support status plus a scope note, with
            # article citations carried as text in vendor_knowledge.py.
            # (Fabricating unverifiable article URLs is forbidden.)
            assert e.get("verification_status") == "code_supported", code
            assert e.get("support_level") == "limited_diagnostic", code


def test_operational_entry_completeness():
    for e in _operational_entries(get_catalog()):
        assert e.get("event_id"), "operational entry without event_id"
        assert e.get("title"), e.get("event_id")
        assert e.get("provider"), e.get("event_id")
        assert e.get("description"), e.get("event_id")


def test_entry_41_never_blames_power_loss_alone():
    by_id = {str(e.get("event_id")): e for e in _operational_entries(get_catalog())}
    desc = str(by_id["41"].get("description", "")).lower()
    causes_named = sum(k in desc for k in ("crash", "power", "reset", "forced", "bugcheck"))
    assert causes_named >= 2, "41 must name several possible causes, not power loss alone"


def test_entry_1129_stays_grouppolicy_qualified():
    by_id = {str(e.get("event_id")): e for e in _operational_entries(get_catalog())}
    assert "GroupPolicy" in str(by_id["1129"].get("provider"))


def test_reference_hosts_are_vendor_or_pinned_source():
    bad = []
    for e in get_catalog():
        ident = str(e.get("diagnostic_code") or e.get("event_id"))
        if e.get("verification_status") == "preserved_legacy":
            continue  # legacy operational entries carry no per-entry URLs
        for url in _ref_urls(e):
            host = _host(url)
            if not host or not str(url).lower().startswith("https://"):
                bad.append((ident, url, "not-https-or-unparseable"))
                continue
            if host in OFFICIAL_HOSTS:
                continue
            if host == "fortinetweb.s3.amazonaws.com" and "docs.fortinet.com" in str(url):
                continue  # Fortinet documentation CDN
            if host == "github.com" and str(url).startswith(
                "https://github.com/openssh/openssh-portable/"
            ):
                continue  # upstream source for log-format facts (pin version later)
            bad.append((ident, url, "unapproved-host"))
    assert not bad, f"unapproved reference hosts: {bad[:5]}"


def test_status_vocabulary_is_known():
    known_verification = {
        "official_documentation_verified",
        "code_supported",
        "code_supported_with_contextual_reference",
    }
    known_support = {"documented_reference", "limited_diagnostic"}
    for e in _vendor_entries(get_catalog()):
        assert e.get("verification_status") in known_verification, e.get("diagnostic_code")
        assert e.get("support_level") in known_support, e.get("diagnostic_code")
