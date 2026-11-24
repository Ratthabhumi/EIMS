"""One-off, idempotent: attach source-bound diagnostic_guidance to four Cisco ASA candidates.

Content comes only from docs/knowledge/CANDIDATE_SOURCE_VERIFICATION_20261119.md (Cisco page text).
Lifecycle is untouched: records stay candidates; no review state is written.
"""
import json
from pathlib import Path

P = Path("backend/domain/analyzer/services/diagnostic_knowledge_catalog.json")
BASIS = ("Cisco Secure Firewall ASA Series Syslog Messages (page updated 2026-09-22), text collected 2026-11-19 by a "
         "model-extracted page fetch; human re-read pending. No software version is stated on the page.")
G = {
    "106023": {
        "expected_findings": ["Message names the denied protocol, source, destination and the access-group that denied the packet.",
                              "Appears even when logging is not enabled on the ACL."],
        "safe_remediation": ["None required for a single deny: it is policy behaviour. Repeated denies from one source might indicate footprinting or port scanning (source wording); correlate before escalating."],
        "risk": "Relaxing an ACL to stop the message widens access; change only after confirming the flow is intended.",
        "rollback": "Restore the previous ACL entry.",
        "verification_criteria": ["For an intended flow: the connection is built (302013) and no further 106023 for that tuple."],
    },
    "106024": {
        "expected_findings": ["ACL compilation ran out of memory; the previously compiled lists stay in use and changes since the last successful compilation are removed."],
        "safe_remediation": ["Remove rules (ACL, AAA, ICMP, SSH and Telnet rule types all count toward the limit), then re-apply the removed changes in smaller steps."],
        "risk": "Changes made since the last successful compilation are not active; removing rules changes enforcement.",
        "rollback": "Keep a copy of the configuration before removing rules and restore it if enforcement regresses.",
        "verification_criteria": ["A later ACL compilation completes without message 106024 (inference; the source page does not state a check)."],
    },
    "302013": {
        "expected_findings": ["A TCP connection was built for the logged endpoints; this does not prove application success."],
        "safe_remediation": ["None required (source wording)."],
        "risk": "Not applicable: informational record.",
        "rollback": "Not applicable.",
        "verification_criteria": ["Correlate with the matching teardown (302014) by connection ID."],
    },
    "302014": {
        "expected_findings": ["A TCP connection was torn down with a reason (for example Conn-timeout means the inactivity timer expired)."],
        "safe_remediation": ["None required (source wording); investigate only when the teardown reason is unexpected for the flow."],
        "risk": "Not applicable: informational record.",
        "rollback": "Not applicable.",
        "verification_criteria": ["The teardown reason matches the expected end of the session."],
    },
}


def main():
    text = P.read_text(encoding="utf-8")
    data = json.loads(text)
    for entry in data["entries"]:
        if entry["source_family"] == "cisco_asa" and entry["diagnostic_code"] in G:
            entry["diagnostic_guidance"] = {**G[entry["diagnostic_code"]], "evidence_basis": BASIS}
    out = json.dumps(data, indent=2, ensure_ascii=False)
    P.write_bytes(out.replace("\n", "\r\n").encode("utf-8"))
    print("updated", sorted(G))


if __name__ == "__main__":
    main()


# ---- second batch (2026-11-20): only wording the 2026-11-19 source collection supports ----
EXTRA_BASIS = {
    ("cisco_asa", "113005"): BASIS,
    ("cisco_asa", "113019"): BASIS,
    ("linux_syslog", "AUTH-FAIL"): ("OpenSSH portable auth.c (auth_log) format string, master branch (unpinned), read 2026-11-19 "
                                    "via a model-extracted fetch; source code, not vendor documentation; human re-read pending."),
}
EXTRA = {
    ("cisco_asa", "113005"): {
        "expected_findings": ["Two variants exist: AAA authentication rejected and AAA authorization rejected; the message names which.",
                              "The username is hidden when it is invalid or unknown."],
        "safe_remediation": ["Retry the authentication / authorization (source wording); then check the AAA server result for the same attempt."],
        "risk": "Repeated retries with a wrong secret can lock the account on the AAA server.",
        "rollback": "Not applicable: a retry changes no configuration.",
        "verification_criteria": ["The retried attempt is accepted and no further 113005 appears for the same user and source."],
    },
    ("cisco_asa", "113019"): {
        "expected_findings": ["Group, username, IP, session type, duration, bytes transmitted/received and a disconnect reason.",
                              "Per the source the message indicates when and why the longest idle user is disconnected."],
        "safe_remediation": ["None required unless the disconnect reason indicates a problem (source wording)."],
        "risk": "Not applicable: informational unless the reason shows a fault.",
        "rollback": "Not applicable.",
        "verification_criteria": ["The reason matches the expected session end (for example idle timeout) for that user."],
    },
    ("linux_syslog", "AUTH-FAIL"): {
        "expected_findings": ["Text of the form '<Accepted|Failed|Partial|Postponed> <method> for [invalid user ]<name> from <ip> port <n> ssh2'.",
                              "'invalid user' is inserted when the account is not valid on the host."],
        "safe_remediation": [],
        "risk": "Blocking a source address on one failed attempt can lock out legitimate users.",
        "rollback": "Not applicable: this record carries no remediation.",
        "verification_criteria": ["Inference: repeated failures from one source stop after any control the engineer applies."],
    },
}


def apply_extra():
    text = P.read_text(encoding="utf-8")
    data = json.loads(text)
    done = []
    for entry in data["entries"]:
        key = (entry["source_family"], entry["diagnostic_code"])
        if key in EXTRA:
            entry["diagnostic_guidance"] = {**EXTRA[key], "evidence_basis": EXTRA_BASIS[key]}
            done.append(key)
    out = json.dumps(data, indent=2, ensure_ascii=False)
    P.write_bytes(out.replace("\n", "\r\n").encode("utf-8"))
    print("second batch:", done)


if __name__ == "__main__":
    apply_extra()
