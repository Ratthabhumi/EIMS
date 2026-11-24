"""Provider-aware Windows retrieval: Event ID alone is never a direct match; stable catalog IDs are unchanged."""
from tests import catalog_expectations as X
import asyncio
from types import SimpleNamespace

import pytest

from backend.domain.analyzer.services.event_knowledge import get_curated_summary
from backend.domain.analyzer.services.operational_catalog import (
    load_catalog, normalize_provider, resolve_windows_entry,
)
from backend.domain.knowledge.retrieval import retrieve_windows


def run(coro):
    return asyncio.run(coro)


def test_stable_ids_unchanged_by_provider_data():
    ids = {e["catalog_id"] for e in load_catalog()}
    assert len(ids) == X.TOTAL and X.BASELINE_IDS <= ids  # growth is allowed; the 163-ID baseline is pinned
    assert "windows_event:official_event_id:1000" in ids
    assert "windows_event:official_event_id:1026" in ids
    # Provider-qualified identities exist only for the two migrated records whose plain ID is already taken.
    assert {i for i in ids if i.count(":") > 2 and i.startswith("windows_event")} == {
        "windows_event:official_event_id:5011:Microsoft-Windows-WAS",
        "windows_event:official_event_id:1001:Microsoft-Windows-WER-SystemErrorReporting"}


@pytest.mark.parametrize("value,expected", [
    ("", ""), (None, ""), ("Unknown", ""), ("  .NET   Runtime ", ".net runtime"),
    ("Microsoft-Windows-GroupPolicy", "grouppolicy"), ("Application Error", "application error"),
])
def test_normalize_provider(value, expected):
    assert normalize_provider(value) == expected


@pytest.mark.parametrize("event_id,provider,basis,kind", [
    ("1000", "Application Error", "provider_and_id", "direct"),
    ("1000", "application error", "provider_and_id", "direct"),
    ("1000", ".NET Runtime", "provider_mismatch", "none"),
    ("1000", "Microsoft-Windows-Foo", "provider_mismatch", "none"),
    ("1000", "Unknown", "provider_unspecified", "contextual"),
    ("1000", "", "provider_unspecified", "contextual"),
    ("1001", "Windows Error Reporting", "provider_and_id", "direct"),
    ("1001", "Microsoft-Windows-WER-SystemErrorReporting", "provider_and_id", "direct"),   # its own record since 2B
    ("1001", "Some-Other-Provider", "provider_mismatch", "none"),
    ("1001", None, "provider_ambiguous", "none"),                                          # two providers share 1001
    ("5011", "Microsoft-Windows-WAS", "provider_and_id", "direct"),
    ("5011", "Microsoft-Windows-Windows Defender", "provider_and_id", "direct"),
    ("5011", "", "provider_ambiguous", "none"),
    ("1026", ".NET Runtime", "provider_and_id", "direct"),
    ("1026", "Application Error", "provider_mismatch", "none"),
    ("1026", "Windows Error Reporting", "provider_mismatch", "none"),
    ("4624", "Microsoft-Windows-Security-Auditing", "provider_and_id", "direct"),
    ("4624", "Service Control Manager", "provider_mismatch", "none"),
    ("7036", "Service Control Manager", "provider_and_id", "direct"),
    ("1058", "Microsoft-Windows-GroupPolicy", "provider_and_id", "direct"),
    ("4199", "Tcpip", "provider_unverified", "contextual"),   # record has no verified provider names: never "mismatch"
    ("999999", "Anything", "no_record", "none"),
])
def test_resolution_matrix(event_id, provider, basis, kind):
    found = resolve_windows_entry(event_id, provider)
    assert (found["basis"], found["kind"]) == (basis, kind)
    if kind == "none" and basis == "provider_mismatch":
        assert found["entry"] is not None  # kept only for traceability, never returned as a match


@pytest.mark.parametrize("event_id,provider", [("1000", ".NET Runtime"), ("1001", "Some-Other-Provider"),
                                               ("1026", "Application Error")])
def test_wrong_provider_is_never_presented_as_a_match(event_id, provider):
    result = run(retrieve_windows(None, event_id, provider))
    assert result["classification"] == "no_verified_match"
    assert result["catalogId"] is None
    assert result["matchKind"] == "none" and result["matchBasis"] == "provider_mismatch"
    assert "not applied" in result["note"]


@pytest.mark.parametrize("event_id,provider,catalog_id", [
    ("1000", "Application Error", "windows_event:official_event_id:1000"),
    ("1001", "Windows Error Reporting", "windows_event:official_event_id:1001"),
    ("1026", ".NET Runtime", "windows_event:official_event_id:1026"),
])
def test_correct_provider_is_a_direct_context_match(event_id, provider, catalog_id):
    result = run(retrieve_windows(None, event_id, provider))
    assert (result["classification"], result["catalogId"]) == ("context_match", catalog_id)
    assert (result["matchKind"], result["matchBasis"]) == ("direct", "provider_and_id")


def test_missing_provider_is_contextual_and_says_so():
    result = run(retrieve_windows(None, "1000", "Unknown"))
    assert result["matchKind"] == "contextual" and result["matchBasis"] == "provider_unspecified"
    assert result["catalogId"] == "windows_event:official_event_id:1000"
    assert "provider" in result["note"].lower() and "reference only" in result["note"]
    assert result["classification"] == "context_match"  # context material is never upgraded to a diagnosis


def test_unknown_event_id_has_no_match():
    result = run(retrieve_windows(None, "999999", "Application Error"))
    assert (result["classification"], result["matchKind"], result["matchBasis"]) == ("no_verified_match", "none", "no_record")


def test_curated_summary_is_suppressed_only_for_a_proven_wrong_provider():
    assert get_curated_summary("1000", "en") is not None                          # legacy call unchanged
    assert get_curated_summary("1000", "en", "Application Error") is not None
    assert get_curated_summary("1000", "en", "Unknown") is not None               # unspecified: unchanged behaviour
    assert get_curated_summary("1000", "en", ".NET Runtime") is None              # proven different provider
    assert get_curated_summary("4624", "en", "Microsoft-Windows-Security-Auditing") is not None
    assert get_curated_summary("4624", "en", "Service Control Manager") is None


def test_non_windows_retrieval_is_unchanged():
    from backend.api.routers.analyzer.analyze import _knowledge_match
    meta = SimpleNamespace(sourceFamily="cisco_asa", eventId="106023", diagnosticCode="106023", provider="ASA",
                           attributes={"deviceType": "ASA", "codeType": "official_message_id"})
    result = run(_knowledge_match(None, meta))
    # With no database the overlay is unavailable, which can only lower trust; the identity match itself is direct.
    assert result.catalogId == "cisco_asa:official_message_id:106023"
    assert result.overlayAvailable is False
    assert result.classification == "diagnostic_candidate_match"
    assert (result.matchKind, result.matchBasis) == ("direct", "identity")


@pytest.mark.parametrize("provider,expected", [
    ("Application Error", ("direct", "windows_event:official_event_id:1000")),
    (".NET Runtime", ("none", None)),
    ("Unknown", ("contextual", "windows_event:official_event_id:1000")),
])
def test_analyzer_entry_point_uses_provider(provider, expected):
    from backend.api.routers.analyzer.analyze import _knowledge_match
    meta = SimpleNamespace(sourceFamily="windows_event", eventId="1000", diagnosticCode="1000", provider=provider,
                           attributes={})
    result = run(_knowledge_match(None, meta))
    assert (result.matchKind, result.catalogId) == expected
