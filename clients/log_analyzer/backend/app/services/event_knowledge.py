import json
import os
from app.schemas.analyze import SolutionSummary

# Load EVENT_KNOWLEDGE from JSON
json_path = os.path.join(os.path.dirname(__file__), 'event_knowledge.json')

EVENT_KNOWLEDGE = {}
try:
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        for evt_id, langs in raw_data.items():
            EVENT_KNOWLEDGE[evt_id] = {}
            for lang, data in langs.items():
                EVENT_KNOWLEDGE[evt_id][lang] = SolutionSummary(
                    overview=data.get("overview", ""),
                    causes=data.get("causes", []),
                    steps=data.get("steps", [])
                )
except Exception as e:
    print(f"Failed to load event_knowledge.json: {e}")


def get_curated_summary(event_id: str, language: str) -> SolutionSummary | None:
    # Map other DCOM errors to 10016's knowledge base
    if event_id in ("10005", "10009", "10028"):
        event_id = "10016"
        
    if event_id not in EVENT_KNOWLEDGE:
        return None
    lang = language if language in ("th", "en") else "th"
    
    return EVENT_KNOWLEDGE[event_id].get(lang)
