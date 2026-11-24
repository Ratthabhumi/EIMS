import json
import os
from backend.domain.analyzer.schemas.analyze import SolutionSummary

# Load EVENT_KNOWLEDGE from JSON
json_path = os.path.join(os.path.dirname(__file__), 'event_knowledge.json')

EVENT_KNOWLEDGE = {}
# Provider(s) each curated entry was written for. Entries without providers (e.g. non-Windows JP1 codes) are unscoped.
EVENT_KNOWLEDGE_PROVIDERS: dict[str, list[str]] = {}
try:
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        for evt_id, langs in raw_data.items():
            EVENT_KNOWLEDGE[evt_id] = {}
            EVENT_KNOWLEDGE_PROVIDERS[evt_id] = list(langs.get("provider_names", []))
            for lang, data in langs.items():
                if lang == "provider_names":
                    continue
                EVENT_KNOWLEDGE[evt_id][lang] = SolutionSummary(
                    overview=data.get("overview", ""),
                    causes=data.get("causes", []),
                    steps=data.get("steps", [])
                )
except Exception as e:
    print(f"Failed to load event_knowledge.json: {e}")


def _legacy_curated_summary(event_id: str, language: str, provider: str | None = None) -> SolutionSummary | None:
    """Reads event_knowledge.json directly. Compatibility layer: used only for identities that have no canonical record
    carrying the curated guidance (the two deferred Hitachi JP1 message IDs) and as the reference for parity tests."""
    if event_id in ("10005", "10009", "10028"):
        event_id = "10016"
    if event_id not in EVENT_KNOWLEDGE:
        return None
    if provider is not None:
        # A summary written for one provider must not describe the same Event ID from another provider, and an
        # unstated provider must not pick one of several providers' meanings of the same ID.
        from backend.domain.analyzer.services.operational_catalog import normalize_provider, resolve_windows_entry
        names = {normalize_provider(n) for n in EVENT_KNOWLEDGE_PROVIDERS.get(event_id, [])}
        given = normalize_provider(provider)
        if given and names and given not in names:
            return None
        if not given and resolve_windows_entry(event_id, provider)["basis"] == "provider_ambiguous":
            return None
    lang = language if language in ("th", "en") else "th"
    template = EVENT_KNOWLEDGE[event_id].get(lang)
    return template.model_copy(deep=True) if template is not None else None


def _canonical_curated_summary(event_id: str, language: str, provider: str | None) -> tuple[bool, SolutionSummary | None]:
    """(handled, summary) from the CANONICAL operational catalog (single source of truth for curated guidance).

    ``handled`` is False when no canonical record carries curated guidance for this Event ID, so the legacy layer may
    answer. Matching is no broader than before: a stated provider must be one of the record's VERIFIED provider names;
    an unstated provider never picks between several providers' records.
    """
    from backend.domain.analyzer.services.operational_catalog import WINDOWS_BY_EVENT_ID, _label_keys, normalize_provider

    def verified_names(entry):
        # Verified provider names when the record lists them, else its provider label (same rule as the resolver).
        names = {normalize_provider(n) for n in entry.get("provider_names") or []}
        return names or _label_keys(entry.get("provider", ""))

    candidates = [e for e in WINDOWS_BY_EVENT_ID.get(str(event_id), [])
                  if ((e.get("diagnostic_guidance") or {}).get("localized_summary"))]
    if not candidates:
        return False, None
    given = normalize_provider(provider) if provider is not None else ""
    if given:
        chosen = [e for e in candidates if given in verified_names(e)]
        if len(chosen) != 1:
            return True, None  # other provider, or ambiguous: never borrow another provider's guidance
        entry = chosen[0]
    else:
        if provider is not None and len(WINDOWS_BY_EVENT_ID.get(str(event_id), [])) > 1:
            return True, None  # several providers share this ID and none was stated
        if len(candidates) != 1:
            return True, None
        entry = candidates[0]
    lang = language if language in ("th", "en") else "th"
    carried = entry["diagnostic_guidance"]["localized_summary"].get(lang)
    if not carried:
        return True, None
    return True, SolutionSummary(overview=carried.get("overview", ""), causes=list(carried.get("causes", [])),
                                 steps=list(carried.get("steps", [])))


def get_curated_summary(event_id: str, language: str, provider: str | None = None) -> SolutionSummary | None:
    """Curated Windows guidance, served from the canonical catalog (legacy file only for non-catalog identities)."""
    if event_id in ("10005", "10009", "10028"):  # other DCOM errors share 10016's knowledge
        event_id = "10016"
    handled, summary = _canonical_curated_summary(event_id, language, provider)
    if handled:
        return summary  # already a fresh copy: shared templates are never handed out
    return _legacy_curated_summary(event_id, language, provider)
