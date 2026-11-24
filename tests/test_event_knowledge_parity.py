"""Second-store parity: everything the Analyzer can say from event_knowledge.json exists in the canonical catalog.

event_knowledge.json is NOT retired by this work; these tests define the bar for retiring it.
"""
import json
from pathlib import Path

import pytest

from backend.domain.analyzer.services.event_knowledge import EVENT_KNOWLEDGE_PROVIDERS, get_curated_summary
from backend.domain.analyzer.services.operational_catalog import (
    WINDOWS_BY_EVENT_ID, normalize_provider, resolve_windows_entry,
)

CURATED = json.loads((Path(__file__).resolve().parents[1] / "backend/domain/analyzer/services/event_knowledge.json")
                     .read_text(encoding="utf-8"))
NON_WINDOWS = {"KAVT0000", "KAVT0245-E"}          # Hitachi JP1 message IDs: deferred, need a vendor family + source
CORRECTED = {"5011", "109"}                        # migrated with corrected text; the curated wording is unsupported


def _canonical_record(eid):
    """The canonical record that should carry this curated entry (matching provider)."""
    for name in CURATED[eid]["provider_names"]:
        found = resolve_windows_entry(eid, name)
        if found["basis"] == "provider_and_id":
            return found["entry"]
    return None


def test_every_curated_windows_entry_has_a_provider_and_a_canonical_record():
    missing = [e for e in CURATED if e not in NON_WINDOWS and not CURATED[e].get("provider_names")]
    assert not missing, f"curated entries without provider: {missing}"
    orphans = [e for e in CURATED if e not in NON_WINDOWS and _canonical_record(e) is None]
    assert not orphans, f"curated entries with no canonical record for their provider: {orphans}"


@pytest.mark.parametrize("eid", sorted(set(CURATED) - NON_WINDOWS - CORRECTED))
def test_curated_content_is_carried_verbatim_by_the_canonical_record(eid):
    rec = _canonical_record(eid)
    carried = rec["diagnostic_guidance"]["localized_summary"]
    for lang in ("th", "en"):
        want = CURATED[eid][lang]
        assert carried[lang]["overview"] == want["overview"]
        assert carried[lang]["causes"] == want.get("causes", [])
        assert carried[lang]["steps"] == want.get("steps", [])
    assert rec["knowledge_class"] == "operational_context"          # migration never promotes
    assert rec["lifecycle_status"] == "operational_context"


@pytest.mark.parametrize("eid", sorted(CORRECTED))
def test_corrected_entries_are_marked_as_corrected(eid):
    rec = _canonical_record(eid)
    assert "CORRECTED" in rec["diagnostic_guidance"]["evidence_basis"]
    carried = rec["diagnostic_guidance"]["localized_summary"]["en"]["overview"]
    assert carried != CURATED[eid]["en"]["overview"]
    if eid == "5011":
        assert "ping" not in carried.lower() and "hung" not in carried.lower()


def test_curated_summary_follows_the_events_provider():
    assert get_curated_summary("5011", "en", "Microsoft-Windows-WAS") is not None
    assert get_curated_summary("5011", "en", "Microsoft-Windows-Windows Defender") is None     # Defender 5011 != IIS text
    assert get_curated_summary("5011", "en", "") is None                                          # ambiguous: two providers
    assert get_curated_summary("1001", "en", "Microsoft-Windows-WER-SystemErrorReporting") is not None
    assert get_curated_summary("1001", "en", "Windows Error Reporting") is None                  # WER 1001 != BugCheck text
    assert get_curated_summary("1001", "en", None) is not None                                    # legacy call (no provider) unchanged
    assert get_curated_summary("1000", "en", ".NET Runtime") is None
    assert get_curated_summary("10005", "en", "Microsoft-Windows-DistributedCOM") is not None     # DCOM alias unchanged


def test_providers_declared_in_the_second_store_match_the_catalog():
    for eid, names in EVENT_KNOWLEDGE_PROVIDERS.items():
        if eid in NON_WINDOWS:
            continue
        rec = _canonical_record(eid)
        assert rec is not None
        for name in names:
            assert resolve_windows_entry(eid, name)["basis"] == "provider_and_id", (eid, name)
