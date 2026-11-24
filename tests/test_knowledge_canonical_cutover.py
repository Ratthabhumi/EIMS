"""Before/after proof for the cutover of curated Windows guidance to the canonical catalog.

The legacy reader is retained as the reference. For every one of the 39 curated records, both languages and every
provider scenario, the canonical-backed answer must equal the legacy answer, except the two deliberately corrected
records (5011, 109) whose canonical text replaces unsupported legacy wording. Nothing is broadened.
"""
import json
from pathlib import Path

import pytest

from backend.domain.analyzer.services import event_knowledge as ek
from backend.domain.analyzer.services.operational_catalog import WINDOWS_BY_EVENT_ID

CURATED = json.loads((Path(__file__).resolve().parents[1] / "backend/domain/analyzer/services/event_knowledge.json")
                     .read_text(encoding="utf-8"))
NON_WINDOWS = {"KAVT0000", "KAVT0245-E"}
CORRECTED = {"5011", "109"}


def _dump(summary):
    return None if summary is None else summary.model_dump()


def _scenarios(eid):
    names = CURATED[eid].get("provider_names", [])
    return [None, "", "Unknown", "Totally Different Provider", *names, *(n.upper() for n in names)]


@pytest.mark.parametrize("eid", sorted(CURATED))
@pytest.mark.parametrize("lang", ["th", "en", "xx"])
def test_canonical_answer_equals_legacy_answer_for_all_providers(eid, lang):
    for provider in _scenarios(eid):
        new = _dump(ek.get_curated_summary(eid, lang, provider))
        old = _dump(ek._legacy_curated_summary(eid, lang, provider))
        if eid in CORRECTED and new is not None and old is not None:
            assert new != old, "corrected record must differ (unsupported legacy wording replaced)"
            continue
        assert new == old, (eid, lang, provider)


def test_no_identity_is_lost_or_broadened():
    for eid in CURATED:
        if eid in NON_WINDOWS:
            assert ek.get_curated_summary(eid, "en") is not None  # served by the legacy compatibility layer
            assert not WINDOWS_BY_EVENT_ID.get(eid)                # still honestly outside the canonical catalog
            continue
        assert ek.get_curated_summary(eid, "en", CURATED[eid]["provider_names"][0]) is not None
        assert ek.get_curated_summary(eid, "en", "Another Provider") is None


def test_callers_never_receive_a_shared_template():
    first = ek.get_curated_summary("4625", "en", CURATED["4625"]["provider_names"][0])
    first.overview = "MUTATED"
    again = ek.get_curated_summary("4625", "en", CURATED["4625"]["provider_names"][0])
    assert again.overview != "MUTATED"


def test_dcom_aliases_still_share_the_10016_guidance():
    provider = CURATED["10016"]["provider_names"][0]
    base = _dump(ek.get_curated_summary("10016", "en", provider))
    for alias in ("10005", "10009", "10028"):
        assert _dump(ek.get_curated_summary(alias, "en", provider)) == base
