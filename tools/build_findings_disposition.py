"""Build the findings disposition register: one row per Round-2 baseline finding plus every new finding raised by the
stricter Round-3 rules. Nothing is merged and nothing is silenced: a finding only becomes RESOLVED_BY_EVIDENCE when it
no longer appears in a fresh validator run *because evidence now exists*; stricter replacement rules are reported as OPEN.

Dispositions: FIX_REQUIRED, EVIDENCE_REQUIRED, ACCEPTED_LIMITATION, NOT_APPLICABLE, BLOCKED, NEEDS_HUMAN_REVIEW.
Resolution status: RESOLVED_BY_EVIDENCE, CLOSED_ACCEPTED_LIMITATION, CLOSED_NOT_APPLICABLE, OPEN_BLOCKED, OPEN_NEEDS_HUMAN_REVIEW.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CERT = ROOT / "docs" / "acceptance" / "certification"
SERVICES = ROOT / "backend" / "domain" / "analyzer" / "services"

# Statements verified against their source page on 2026-11-22 (scripted fetch; human re-read still pending).
ALWAYS_NEVER = {
    "candidate:veeam-vbr:proxy:no-proxy-available-vmware": (
        "ACCEPTED_LIMITATION", "CLOSED_ACCEPTED_LIMITATION",
        "The record says the vendor KB states the error 'nearly always' happens with manually configured proxies. Source https://www.veeam.com/kb1857 "
        "contains 'This error nearly always occurs when proxies have been manually configured to use a specific Transport Mode'. The wording is "
        "qualified ('nearly') and attributed to the KB, so no condition is missing.",
        "Regex matched a vendor-qualified frequency statement ('nearly always'); wording unchanged.", "Human re-read of KB1857 pending."),
    "candidate:fortinet-fortios:traffic:policyid-0-forward-implicit-deny": (
        "NOT_APPLICABLE", "CLOSED_NOT_APPLICABLE",
        "The matched word is the literal FortiOS default object name 'Default Schedule: always' quoted from the vendor page, not a claim about behaviour.",
        "Keyword false positive (a configuration object name).", "None for this finding."),
    "reference:haproxy:termination_state_first_char:I": (
        "ACCEPTED_LIMITATION", "CLOSED_ACCEPTED_LIMITATION",
        "The description is copied verbatim from https://docs.haproxy.org/2.8/configuration.html (checked 2026-11-22): 'an internal error was identified by the "
        "proxy during a self-check. This should NEVER happen ... It would be wise to preventively restart the process ...'. The record attributes it to HAProxy "
        "('HAProxy documents ...'); the emphasis is the vendor's, not an EIMS claim.",
        "Verbatim vendor emphasis; keyword match only. Note the quoted text advises restarting the process.", "Human re-read pending; reviewer to confirm the restart advice is acceptable to show."),
}
REPLACED_BY = {"parser_match_coverage_missing": "state_real_evidence_positive_missing",
               "parser_non_match_coverage_missing": "state_real_evidence_negative_missing"}


def _windows_dispositions() -> dict[tuple[str, str], dict]:
    rows = json.loads((SERVICES / "windows_reference_dispositions.json").read_text(encoding="utf-8"))["records"]
    return {(r["event_id"], r["provider"]): r for r in rows}


def build(baseline: list[dict], current: list[dict], register: dict, sources: dict, round3: list[dict] | None = None, ledger: dict | None = None) -> list[dict]:
    reg = {r["record_key"]: r for r in register["records"]}
    now = {(f.get("record_key"), f["code"]): f for f in current if f["severity"] != "evidence"}
    now_by_record: dict[str, set[str]] = {}
    for rk, code in now:
        now_by_record.setdefault(rk, set()).add(code)
    win = _windows_dispositions()
    rows: list[dict] = []
    r3set = {(f.get("record_key"), f["code"]) for f in (round3 or []) if f["severity"] != "evidence"}
    led = {d["record_key"]: d for d in (ledger or {}).get("dispositions", [])}

    def ledger_note(key: str) -> str:
        d = led.get(key)
        if not d:
            return ""
        return (f" Round-4 research ledger: {d['ledger_disposition']} - {d['reason']}; Microsoft Learn search candidates checked with no match: "
                f"{len(d.get('search_candidates_checked_no_match', []))}.")

    def row(key, code, origin, message, **kw):
        r = reg.get(key, {})
        rows.append({"record_key": key, "class": r.get("cert_class", ""), "finding_type": code, "origin": origin,
                     "finding_message": message, **kw})

    def windows_case(key):
        raw = sources[key][1]
        d = win.get((raw.get("event_id"), raw.get("provider")), {})
        return raw, d

    seen = set()
    for f in baseline:
        key, code = f.get("record_key"), f["code"]
        seen.add((key, code))
        still = (key, code) in now
        evidence_files = sorted({t["evidence_file"] for t in reg.get(key, {}).get("test_evidence", [])})
        if code == "reference_parser_check_summary":
            row("(register)", code, "round2_baseline", f["message"], value_before="1 informational summary row counted among the 132",
                value_after="reported separately as informational_evidence_rows", evidence="validator output",
                root_cause="The Round-2 finding count included one evidence summary row that is not a defect.",
                recommended_action="None.", disposition="NOT_APPLICABLE", resolution_status="CLOSED_NOT_APPLICABLE", remaining_blocker="")
        elif code in ("parser_match_coverage_missing", "parser_non_match_coverage_missing"):
            polarity = "positive" if code == "parser_match_coverage_missing" else "negative"
            cls = reg[key]["cert_class"]
            replaced = REPLACED_BY[code] in now_by_record.get(key, set())
            unmapped = "evaluator_not_mapped" in now_by_record.get(key, set())
            if cls == "B" and not still:
                kind = "parser_match" if polarity == "positive" else "parser_non_match"
                cases = [t for t in reg[key]["test_evidence"] if t["kind"] == kind]
                row(key, code, "round2_baseline", f["message"], value_before="test_evidence: []",
                    value_after="; ".join(f"{t['kind']} x{t['cases']} passed={t['all_passed']} current={t['current']} ({t['evidence_file']})" for t in cases),
                    evidence=f"Run-bound evidence {', '.join(evidence_files)}; bound to content hash {reg[key]['content_hash'][:12]}.",
                    root_cause="The register had no run-bound per-record evidence; tests existed but were not bound to the record.",
                    recommended_action="Keep the fixtures in tests/certification_fixtures.py and re-run tools/run_certification_matching.py after any content change.",
                    disposition="EVIDENCE_REQUIRED", resolution_status="RESOLVED_BY_EVIDENCE", remaining_blocker="")
            elif cls == "D" and unmapped:
                row(key, code, "round2_baseline", f["message"], value_before="test_evidence: []", value_after="still empty; superseded by evaluator_not_mapped",
                    evidence="parser_or_evaluator mapping is candidate_for_future_integration; no parser/evaluator path exists to run.",
                    root_cause="Candidate documents a CLI-state condition (unexpected HA failover causes) with no evaluator or parser mapped.",
                    recommended_action="Do not create parser evidence. Build an evaluator first, then add real-source evidence.",
                    disposition="BLOCKED", resolution_status="OPEN_BLOCKED", remaining_blocker="no evaluator mapped; real HA output unavailable",
                    superseded_by="evaluator_not_mapped")
            elif cls == "D" and replaced:
                row(key, code, "round2_baseline", f["message"], value_before="test_evidence: []",
                    value_after=f"replaced by stricter class-D finding {REPLACED_BY[code]}",
                    evidence="No real-source evidence exists for this evaluator.",
                    root_cause="No FortiGate (or recorded real `get sys ha status` output) is available; authored strings are not real-source evidence.",
                    recommended_action="Obtain real `get sys ha status` output from an authorised FortiGate or lab, then add run-bound evidence.",
                    disposition="BLOCKED", resolution_status="OPEN_BLOCKED", remaining_blocker="real FortiGate HA status output / environment",
                    superseded_by=REPLACED_BY[code])
            elif cls == "D" and not still:
                kinds = [t for t in reg[key]["test_evidence"] if t["kind"].startswith("evaluator_real_state")]
                row(key, code, "round2_baseline", f["message"], value_before="test_evidence: []",
                    value_after="; ".join(f"{t['kind']} x{t['cases']} passed={t['all_passed']} current={t['current']}" for t in kinds),
                    evidence="technical_evidence_pg_state.json: real rows from a disposable PostgreSQL 16 primary+standby.",
                    root_cause="Only authored rows existed; the class-D rule now requires real PostgreSQL output.",
                    recommended_action="Re-run tools/run_certification_pg_state.py after evaluator or record changes.",
                    disposition="EVIDENCE_REQUIRED", resolution_status="RESOLVED_BY_EVIDENCE", remaining_blocker="")
            else:  # still failing, or an unexpected class: never reported as resolved
                row(key, code, "round2_baseline", f["message"], value_before="test_evidence: []", value_after="still empty",
                    evidence="Finding still present in the fresh validator run.",
                    root_cause="Evidence has not been produced for this record.", recommended_action="Produce run-bound evidence or keep BLOCKED.",
                    disposition="BLOCKED", resolution_status="OPEN_BLOCKED", remaining_blocker="evidence not produced")
        elif code in ("version_scope_missing",):
            raw, d = windows_case(key)
            disp = d.get("disposition", "")
            blocked = disp != "NEEDS_HUMAN_REVIEW"
            row(key, code, "round2_baseline", f["message"], value_before="version_scope: ''",
                value_after="unchanged (no evidence to support a scope)",
                evidence=f"windows_reference_dispositions.json: {disp}; {d.get('note', '')[:300]}" + ledger_note(key),
                root_cause=("No exact Microsoft page names this Event ID/provider, so no version applicability can be quoted." if disp == "NO_AUTHORITATIVE_REFERENCE_FOUND"
                            else "Only an indirect page exists; it does not name the Event ID, so its applicability text is not evidence for this event." if disp == "INDIRECT_AUTHORITATIVE_REFERENCE"
                            else "Disposition needs a human to choose the source."),
                recommended_action="Find an exact Microsoft source (or have a human confirm one), then record its stated scope. Do not infer from OS version or file dates.",
                disposition="BLOCKED" if blocked else "NEEDS_HUMAN_REVIEW", resolution_status="OPEN_BLOCKED" if blocked else "OPEN_NEEDS_HUMAN_REVIEW",
                remaining_blocker="NEEDS_SOURCE_CONFIRMATION: " + ("exact source" if disp != "NEEDS_HUMAN_REVIEW" else "human source choice"))
        elif code == "unqualified_always_never":
            disp, status, evidence, cause, blocker = ALWAYS_NEVER[key]
            row(key, code, "round2_baseline", f["message"], value_before="text contains always/never", value_after="text unchanged",
                evidence=evidence, root_cause=cause, recommended_action="No text change: no source-supported condition is missing.",
                disposition=disp, resolution_status=status, remaining_blocker=blocker)
        else:
            raise ValueError(f"unhandled baseline finding code {code}")

    # New findings raised by the stricter Round-3 rules (not in the Round-2 baseline)
    for (key, code), f in sorted(now.items(), key=lambda kv: (kv[0][1], kv[0][0] or "")):
        if (key, code) in seen:
            continue
        origin = "round3_new_rule" if (key, code) in r3set else "round4_new_rule"
        if code == "source_url_missing":
            raw, d = windows_case(key)
            disp = d.get("disposition", "")
            row(key, code, origin, f["message"], value_before="source_urls: []", value_after="unchanged",
                evidence=f"windows_reference_dispositions.json: {disp}." + ledger_note(key), root_cause="No exact source exists for this record (same 42 records as version_scope_missing).",
                recommended_action="Source search per the Windows disposition; human confirmation if found.",
                disposition="NEEDS_HUMAN_REVIEW" if disp == "NEEDS_HUMAN_REVIEW" else "BLOCKED",
                resolution_status="OPEN_NEEDS_HUMAN_REVIEW" if disp == "NEEDS_HUMAN_REVIEW" else "OPEN_BLOCKED", remaining_blocker="exact source")
        elif code == "version_scope_not_explicit":
            raw = sources[key][1]
            row(key, code, origin, f["message"], value_before=str(reg[key].get("version_scope", ""))[:200], value_after="unchanged",
                evidence="version_scope_basis=derived_from_source_scope: the value is the cited page's scope sentence, not a product/version range.",
                root_cause="The Round-2 rule accepted any non-empty text, including a page-scope sentence, as a version scope for records that have an exact reference.",
                recommended_action="Read the cited Microsoft page's applicability statement (if any) and record it explicitly; leave empty if the page states none.",
                disposition="NEEDS_HUMAN_REVIEW", resolution_status="OPEN_NEEDS_HUMAN_REVIEW", remaining_blocker="explicit version applicability to be read from the cited page")
        elif code == "version_scope_product_level_only":
            row(key, code, origin, f["message"], value_before=str(reg[key].get("version_scope", ""))[:200], value_after="unchanged (statement kept verbatim in the catalog applicability block)",
                evidence="Official page 'Applies to' names a product-level scope only (e.g. 'Supported versions of Windows Server'); no OS version or build range is published there.",
                root_cause="The source documents the event without a version range; a product-level scope is not an OS version.",
                recommended_action="Find another official page that states OS/build support for this event, or have a human decide that the product-level scope is sufficient.",
                disposition="BLOCKED", resolution_status="OPEN_BLOCKED", remaining_blocker="no OS/build range in the official source")
        elif code == "destructive_remediation_risk_unresolved":
            raw = sources[key][1]
            row(key, code, origin, f["message"], value_before=str(raw.get("operational_risk", ""))[:200], value_after="unchanged",
                evidence="Remediation contains a state-changing verb; the risk field says the vendor stated no risk. Source scan: risk_warning_evidence.json (keyword scan of the cited page; per-record conclusion is recorded there).",
                root_cause="The Round-2 rule counted any non-empty risk text, including 'Not stated', as a stated risk.",
                recommended_action="Human reviewer decides whether a risk/rollback warning must be added from vendor text.",
                disposition="NEEDS_HUMAN_REVIEW", resolution_status="OPEN_NEEDS_HUMAN_REVIEW", remaining_blocker="reviewer decision on risk wording")
        elif code in ("state_real_evidence_positive_missing", "state_real_evidence_negative_missing"):
            row(key, code, origin, f["message"], value_before="authored-string tests only", value_after="unchanged",
                evidence="Evaluator mapped; no real FortiGate output available in this environment.",
                root_cause="Class-D rule requires real-source evidence; authored strings do not count.",
                recommended_action="Obtain real `get sys ha status` output from an authorised FortiGate/lab.",
                disposition="BLOCKED", resolution_status="OPEN_BLOCKED", remaining_blocker="real FortiGate HA status output / environment")
        elif code == "evaluator_not_mapped":
            row(key, code, origin, f["message"], value_before="candidate_for_future_integration", value_after="unchanged",
                evidence="No evaluator exists for this record.", root_cause="Documented CLI-state condition; evaluator not built.",
                recommended_action="Build an evaluator only if the vendor text supports a deterministic rule; then collect real evidence.",
                disposition="BLOCKED", resolution_status="OPEN_BLOCKED", remaining_blocker="no evaluator")
        else:
            raise ValueError(f"unhandled new finding code {code}")

    # Round-3 findings that no longer appear: resolved by evidence, or replaced by a more precise finding
    for key, code in sorted(r3set - set(now) - seen, key=lambda kv: (kv[1], kv[0] or "")):
        r = reg.get(key, {})
        msg = next((f["message"] for f in (round3 or []) if f.get("record_key") == key and f["code"] == code), "")
        if code == "version_scope_not_explicit" and r.get("version_scope_basis") == "explicit_from_official_statement":
            row(key, code, "round3_new_rule", msg, value_before="page-scope sentence only", value_after=str(r.get("version_scope", ""))[:200],
                evidence="Catalog applicability block copied verbatim from the cited official page (windows_source_research_ledger.json); publication metadata kept separate from the OS statement.",
                root_cause="The record had a source but no extracted applicability statement.",
                recommended_action="Human re-read of the cited page; nothing further for this finding.",
                disposition="EVIDENCE_REQUIRED", resolution_status="RESOLVED_BY_EVIDENCE", remaining_blocker="", resolved_by="official_applicability_statement")
        elif code == "version_scope_not_explicit" and "version_scope_product_level_only" in now_by_record.get(key, set()):
            row(key, code, "round3_new_rule", msg, value_before="page-scope sentence only", value_after="replaced by version_scope_product_level_only",
                evidence="The page's own 'Applies to' line is product-level only.", root_cause="Research found no OS version range.",
                recommended_action="See version_scope_product_level_only.", disposition="BLOCKED", resolution_status="OPEN_BLOCKED",
                remaining_blocker="no OS/build range in the official source", superseded_by="version_scope_product_level_only")
        else:
            raise ValueError(f"round-3 finding {code} for {key} disappeared without a recorded reason")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=CERT / "baseline_round2_findings.json")
    parser.add_argument("--round3", type=Path, default=CERT / "baseline_round3_findings.json")
    parser.add_argument("--ledger", type=Path, default=CERT / "windows_source_research_ledger.json")
    parser.add_argument("--register", type=Path, default=CERT / "register.json")
    parser.add_argument("--output-dir", type=Path, default=CERT)
    args = parser.parse_args(argv)
    from tools.validate_knowledge_certification import _source_lookup, validate_register
    register = json.loads(args.register.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["findings"]
    current = validate_register(register)
    round3 = json.loads(args.round3.read_text(encoding="utf-8"))["findings"] if args.round3.exists() else None
    ledger = json.loads(args.ledger.read_text(encoding="utf-8")) if args.ledger.exists() else None
    rows = build(baseline, current, register, _source_lookup(SERVICES), round3, ledger)
    summary = {
        "baseline_findings": len(baseline),
        "baseline_dispositioned": sum(r["origin"] == "round2_baseline" for r in rows),
        "round3_rows": sum(r["origin"] == "round3_new_rule" for r in rows),
        "round4_new_findings": sum(r["origin"] == "round4_new_rule" for r in rows),
        "unique_records_with_open_findings": len({r["record_key"] for r in rows if r["resolution_status"].startswith("OPEN") and not r.get("superseded_by")}),
        "by_disposition": dict(sorted(Counter(r["disposition"] for r in rows).items())),
        "by_resolution_status": dict(sorted(Counter(r["resolution_status"] for r in rows).items())),
        "by_finding_type": dict(sorted(Counter(r["finding_type"] for r in rows).items())),
    }
    out = {"schema_version": 1, "note": "Dispositions are evidence-based triage, not certification decisions.", "summary": summary, "dispositions": rows}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "findings_disposition.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cols = ["record_key", "class", "finding_type", "origin", "superseded_by", "resolved_by", "value_before", "value_after", "evidence", "root_cause", "recommended_action",
            "disposition", "resolution_status", "remaining_blocker", "finding_message"]
    with (args.output_dir / "findings_disposition.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
