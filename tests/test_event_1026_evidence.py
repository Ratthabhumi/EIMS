"""Event 1026 (.NET Runtime) evidence contract: raw text preserved, repeats grouped (not dropped), references honest."""
from pathlib import Path

from backend.domain.analyzer.services.incident_extract import extract_incident
from backend.domain.analyzer.services.parser import parse_event_metadata

FIXTURE = Path(__file__).with_name("fixtures") / "dotnet_runtime_1026_gcm.txt"
TEXT = FIXTURE.read_text(encoding="utf-8")
FRAMES = ["at System.Linq.ThrowHelper.ThrowNoElementsException()",
          "at GitCredentialManager.Authentication.Select(IList`1 items)",
          "at GitCredentialManager.Program.Main(String[] args)"]


def test_identity_and_runtime_details_are_parsed_verbatim():
    meta = parse_event_metadata(TEXT)
    assert (meta.eventId, meta.provider, meta.logName, meta.computer) == ("1026", ".NET Runtime", "Application", "WS-ENG-01")
    assert meta.timestamp == "11/20/2026 9:14:22 AM"          # stated time, kept as written (no timezone invented)
    assert meta.faultingApp == "git-credential-manager.exe"
    attrs = meta.attributes
    assert attrs["frameworkVersion"] == "v8.0.0" and attrs["application"] == "git-credential-manager.exe"
    assert attrs["exceptionInfo"].startswith("System.InvalidOperationException")
    assert attrs["stackFrames"] == FRAMES                       # stack trace preserved, in order
    assert attrs["exceptionBlockCount"] == 2                    # the repetition is recorded, not hidden


def test_repeated_exception_block_is_grouped_with_every_line_number_kept():
    incident = extract_incident(TEXT, "windows_event")
    texts = incident["evidence"]
    assert len(texts) == len(set(texts)), "evidence strings must not repeat"
    refs = {r["text"]: r for r in incident["evidenceRefs"]}
    exception = refs["Exception Info: System.InvalidOperationException: Sequence contains no elements"]
    assert exception["lineNumbers"] == [14, 18] and exception["occurrences"] == 2
    assert refs["Description: The process was terminated due to an unhandled exception."]["lineNumbers"] == [13]
    for ref in refs.values():
        assert "submitted text" in ref["lineBasis"] and "not an original file offset" in ref["lineBasis"]


def test_raw_submission_is_untouched_by_extraction():
    before = TEXT
    extract_incident(TEXT, "windows_event")
    parse_event_metadata(TEXT)
    assert TEXT == before == FIXTURE.read_text(encoding="utf-8")
    assert TEXT.count("Exception Info:") == 2                  # both blocks still exist in the raw evidence


def test_no_root_cause_is_asserted_from_the_event_alone():
    incident = extract_incident(TEXT, "windows_event")
    assert any("root cause is not established" in u.lower() for u in incident["unknowns"])
    assert not incident["diagnosticSignatures"]


def test_same_message_from_different_sources_or_times_is_not_merged():
    line = "Exception Info: System.InvalidOperationException: Sequence contains no elements"
    text = (f"2026-11-20T01:00:00Z {line}\n2026-11-20T01:05:00Z {line}\n")
    refs = extract_incident(text, "windows_event")["evidenceRefs"]
    assert len(refs) == 2, "different stated times are different occurrences"
    assert {r["timestamp"] for r in refs} == {"2026-11-20T01:00:00Z", "2026-11-20T01:05:00Z"}


def test_missing_metadata_does_not_crash_or_invent_identity():
    meta = parse_event_metadata("The process was terminated due to an unhandled exception.")
    assert meta.eventId in ("", "Unknown") or meta.sourceFamily in ("", "unknown_text")
    assert "recordId" not in (meta.attributes or {})
    assert extract_incident("", "windows_event")["evidenceRefs"] == []


def test_record_id_is_captured_when_the_source_states_it():
    text = TEXT.replace("Computer:      WS-ENG-01", "Computer:      WS-ENG-01\nEvent Record ID: 48213")
    assert parse_event_metadata(text).attributes["recordId"] == "48213"
