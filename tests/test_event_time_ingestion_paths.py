"""Every ingestion path applies the same event-time semantics (request/arrival time is never an event time)."""
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from backend.domain.analyzer.services.import_pipeline import normalize_report_event
from backend.domain.incident.service import EvidenceInput
from backend.domain.incident_ingest import consumer as consumer_mod

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _event(occurrence_time):
    return {"event_id": "1000", "severity_level": "Error", "channel": "Application", "provider": "Application Error",
            "record_id": 7, "message": "m", "occurrence_time": occurrence_time}


@pytest.mark.parametrize("raw, quality", [
    ("2026-11-20T01:02:03Z", "source_aware"),
    ("2026-11-20T08:02:03+07:00", "source_aware"),
    ("2026-11-20T01:02:03", "source_naive"),      # stored as UTC for compatibility, but flagged as untrusted
    (None, "absent"),
    ("garbage", "absent"),
])
def test_offline_import_tags_time_quality(raw, quality):
    assert normalize_report_event(_event(raw))["time_quality"] == quality


class _Service:
    enriched = []

    def __init__(self, session):
        pass

    async def enrich_evidence(self, items, asset_id):
        return items, asset_id

    async def create_from_evidence(self, items, **kw):
        _Service.enriched = items
        return SimpleNamespace(), True


class _Ctx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("quality, confidence", [("absent", "missing"), ("source_naive", "ambiguous")])
async def test_stream_consumer_never_trusts_arrival_or_zoneless_time(monkeypatch, quality, confidence):
    from backend.domain.incident_ingest.envelope import IngestEnvelope
    monkeypatch.setattr(consumer_mod, "IncidentService", _Service)
    envelope = IngestEnvelope(outbox_id=uuid.uuid4(), source_type="winlog", source_id=str(uuid.uuid4()), observed_at=NOW,
                              provenance={"origin": "offline_import", "severity": "Error", "time_quality": quality})
    consumer = consumer_mod.IncidentIngestConsumer(redis_provider=lambda: None, session_maker_provider=lambda: (lambda: _Ctx()),
                                                    max_delivery_attempts=3, reclaim_idle_ms=0)
    await consumer._create_incident(lambda: _Ctx(), envelope)
    item = _Service.enriched[0]
    assert (item.time_confidence, item.event_time) == (confidence, None)


@pytest.mark.asyncio
async def test_stream_consumer_keeps_source_aware_time_as_supplied(monkeypatch):
    from backend.domain.incident_ingest.envelope import IngestEnvelope
    monkeypatch.setattr(consumer_mod, "IncidentService", _Service)
    envelope = IngestEnvelope(outbox_id=uuid.uuid4(), source_type="winlog", source_id=str(uuid.uuid4()), observed_at=NOW,
                              provenance={"origin": "offline_import", "severity": "Error", "time_quality": "source_aware"})
    consumer = consumer_mod.IncidentIngestConsumer(redis_provider=lambda: None, session_maker_provider=lambda: (lambda: _Ctx()),
                                                    max_delivery_attempts=3, reclaim_idle_ms=0)
    await consumer._create_incident(lambda: _Ctx(), envelope)
    item = _Service.enriched[0]
    assert item.time_confidence is None and item.observed_at == NOW  # untouched: resolved as asserted by Incident Core
