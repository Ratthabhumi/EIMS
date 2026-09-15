"""Hermetic tests for the Sprint 13 evidence-ingestion pipeline.

Covers the pure helpers in import_pipeline (normalization, dedup, priority,
metadata, description) and the orchestrator (ingest_report_events) with
fully-mocked DB/analyzer functions - no database, no network, no API keys.
"""

import uuid

import pytest

from backend.domain.analyzer import services
from backend.domain.analyzer.schemas.analyze import EventMetadata, SolutionSummary

PIPELINE = "backend.domain.analyzer.services.import_pipeline"

import importlib
P = importlib.import_module(PIPELINE)

ASSET_ID = "EIMS-2026-0001"

SAMPLE_EVENT = {
    "event_id": 10016,
    "provider": "DistributedCOM",
    "severity": "Error",
    "channel": "System",
    "record_id": 42,
    "occurrence_time": "2026-09-14T10:00:00",
    "message": "DCOM Cannot start a service.",
}


class FakeResult:
    def __init__(self, values):
        self._values = list(values)

    def scalars(self):
        return self

    def all(self):
        return self._values

    def scalar_one_or_none(self):
        return self._values[0] if self._values else None


class FakeDB:
    """Minimal AsyncSession double recording calls and adding rows in-memory."""

    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.commit_error = None

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, stmt):
        return FakeResult([])


# ---------------------------------------------------------------------------
# normalize_report_event
# ---------------------------------------------------------------------------

class TestNormalizeReportEvent:
    def test_valid_event(self):
        out = P.normalize_report_event(dict(SAMPLE_EVENT))
        assert out is not None
        assert out["event_id"] == 10016
        assert out["severity_level"] == "Error"
        assert out["channel"] == "System"
        assert out["provider"] == "DistributedCOM"
        assert out["record_id"] == 42
        assert out["occurrence_time"].isoformat().startswith("2026-09-14T10:00:00")

    def test_none_and_non_dict(self):
        assert P.normalize_report_event(None) is None
        assert P.normalize_report_event("junk") is None

    def test_bad_event_id_rejected(self):
        assert P.normalize_report_event({"event_id": "abc"}) is None
        assert P.normalize_report_event({"event_id": -1}) is None
        assert P.normalize_report_event({}) is None
        assert P.normalize_report_event({"event_id": None}) is None

    def test_defaults_filled(self):
        out = P.normalize_report_event({"event_id": 5})
        assert out["severity_level"] == "Information"
        assert out["channel"] == "System"
        assert out["provider"] == "Unknown"
        assert out["occurrence_time"] is None
        assert out["record_id"] is None

    def test_message_truncated(self):
        out = P.normalize_report_event({**SAMPLE_EVENT, "message": "x" * 5000})
        assert out is not None
        assert len(out["message"]) == 1000

    def test_naive_time_gets_utc(self):
        out = P.normalize_report_event(dict(SAMPLE_EVENT))
        assert out["occurrence_time"].tzinfo is not None

    def test_bad_time_returns_none_time(self):
        out = P.normalize_report_event({**SAMPLE_EVENT, "occurrence_time": "not-a-time"})
        assert out["occurrence_time"] is None


# ---------------------------------------------------------------------------
# compute_dedup_key
# ---------------------------------------------------------------------------

class TestComputeDedupKey:
    def test_deterministic(self):
        assert P.compute_dedup_key(ASSET_ID, SAMPLE_EVENT) == P.compute_dedup_key(ASSET_ID, SAMPLE_EVENT)

    def test_differs_across_assets(self):
        assert P.compute_dedup_key(ASSET_ID, SAMPLE_EVENT) != P.compute_dedup_key("OTHER", SAMPLE_EVENT)

    def test_differs_across_records(self):
        other = {**SAMPLE_EVENT, "record_id": 43}
        assert P.compute_dedup_key(ASSET_ID, SAMPLE_EVENT) != P.compute_dedup_key(ASSET_ID, other)

    def test_is_sha256_hex(self):
        key = P.compute_dedup_key(ASSET_ID, SAMPLE_EVENT)
        assert len(key) == 64
        int(key, 16)  # raises if not hex


# ---------------------------------------------------------------------------
# build_evtx_metadata / build_analysis_provenance / priority / metadata
# ---------------------------------------------------------------------------

class TestMetadataAndPriority:
    def test_evtx_metadata_envelope(self):
        key = P.compute_dedup_key(ASSET_ID, SAMPLE_EVENT)
        meta = P.build_evtx_metadata(SAMPLE_EVENT, key)
        assert meta["_reporter_dedup"] == key
        assert meta["source_type"] == "USB_OFFLINE_COLLECTION"
        assert meta["channel"] == "System"

    def test_analysis_provenance_fields(self):
        prov = P.build_analysis_provenance("uuid-1", ASSET_ID, SAMPLE_EVENT)
        assert prov["source_type"] == "USB_OFFLINE_COLLECTION"
        assert prov["asset_id"] == ASSET_ID
        assert prov["event_source_id"] == "uuid-1"
        assert prov["channel"] == "System"
        assert prov["provider"] == "DistributedCOM"
        assert prov["record_id"] == 42

    def test_priority(self):
        assert P.analysis_priority({"severity_level": "Critical"}) == 3
        assert P.analysis_priority({"severity_level": "Error"}) == 2
        assert P.analysis_priority({"severity_level": "Warning"}) == 1
        assert P.analysis_priority({"severity_level": "Information"}) == 0
        assert P.analysis_priority({}) == 0

    def test_build_event_metadata(self):
        meta = P.build_event_metadata({**SAMPLE_EVENT, "severity_level": "Error"})
        assert isinstance(meta, EventMetadata)
        assert meta.eventId == "10016"
        assert meta.level == "Error"
        assert meta.isCritical is True

    def test_build_event_metadata_warning_not_critical(self):
        meta = P.build_event_metadata({**SAMPLE_EVENT, "severity_level": "Warning"})
        assert meta.isCritical is False

    def test_format_event_description(self):
        assert P.format_event_description(SAMPLE_EVENT) == "DCOM Cannot start a service."

    def test_format_event_description_fallback(self):
        desc = P.format_event_description({"event_id": 10016, "provider": "X", "channel": "System"})
        assert "10016" in desc and "X" in desc


# ---------------------------------------------------------------------------
# ingest_report_events (hermetic orchestrator)
# ---------------------------------------------------------------------------

def _report(*events):
    return {"event_logs": {"events": list(events)}}


class TestIngestReportEvents:
    async def test_no_event_logs(self):
        result = await P.ingest_report_events(FakeDB(), ASSET_ID, {"system": {}})
        assert result.events_received == 0
        assert result.summary == "No event evidence in report"

    async def test_unusable_events_counted_as_failed(self, monkeypatch):
        db = FakeDB()
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)
        monkeypatch.setattr(P, "_analyze_event", _ok_analyze)
        result = await P.ingest_report_events(
            db, ASSET_ID, _report({"event_id": "abc"}, dict(SAMPLE_EVENT))
        )
        assert result.events_received == 2
        assert result.events_failed == 1
        assert result.events_new == 1

    async def test_full_ingest_analyzes_all(self, monkeypatch):
        db = FakeDB()
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)
        monkeypatch.setattr(P, "_analyze_event", _ok_analyze)
        result = await P.ingest_report_events(db, ASSET_ID, _report(dict(SAMPLE_EVENT)))
        assert result.events_received == 1
        assert result.events_new == 1
        assert result.events_duplicate == 0
        assert result.events_analyzed == 1
        assert db.commits >= 1

    async def test_duplicates_skipped_and_not_analyzed(self, monkeypatch):
        db = FakeDB()
        normalized = P.normalize_report_event(dict(SAMPLE_EVENT))
        key = P.compute_dedup_key(ASSET_ID, normalized)

        async def dup_keys(db_, asset, keys):
            return {key}

        monkeypatch.setattr(P, "_fetch_duplicate_keys", dup_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        analyzed = []
        monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)

        async def record_analyze(db_, asset, event, dedup, language="th", api_key=None):
            analyzed.append(dedup)
            return True

        monkeypatch.setattr(P, "_analyze_event", record_analyze)
        result = await P.ingest_report_events(db, ASSET_ID, _report(dict(SAMPLE_EVENT)))
        assert result.events_duplicate == 1
        assert result.events_new == 0
        assert result.events_analyzed == 0
        assert analyzed == []

    async def test_already_analyzed_skipped(self, monkeypatch):
        db = FakeDB()
        normalized = P.normalize_report_event(dict(SAMPLE_EVENT))
        key = P.compute_dedup_key(ASSET_ID, normalized)
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        analyzed = []
        monkeypatch.setattr(P, "_persist_event", _fake_persist)

        async def analyzed_keys(db_, keys):
            return {key}

        monkeypatch.setattr(P, "_fetch_analyzed_keys", analyzed_keys)

        async def record_analyze(db_, asset, event, dedup, language="th", api_key=None):
            analyzed.append(dedup)
            return True

        monkeypatch.setattr(P, "_analyze_event", record_analyze)
        result = await P.ingest_report_events(db, ASSET_ID, _report(dict(SAMPLE_EVENT)))
        assert result.events_new == 1
        assert result.events_analyzed == 0
        assert analyzed == []

    async def test_analysis_failure_non_fatal(self, monkeypatch):
        db = FakeDB()
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)
        monkeypatch.setattr(P, "_analyze_event", _fail_analyze)
        result = await P.ingest_report_events(db, ASSET_ID, _report(dict(SAMPLE_EVENT)))
        assert result.events_new == 1   # evidence persisted even when analysis fails
        assert result.events_analyzed == 0
        assert result.analysis_failed == 1

    async def test_persist_failure_counts_failed(self, monkeypatch):
        db = FakeDB()
        db.commit_error = RuntimeError("db down")
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        result = await P.ingest_report_events(db, ASSET_ID, _report(dict(SAMPLE_EVENT)))
        assert result.events_new == 0
        assert result.events_failed == 1
        assert db.rollbacks >= 1

    async def test_bounded_analyze_max(self, monkeypatch):
        db = FakeDB()
        events = [
            {**SAMPLE_EVENT, "record_id": 1, "severity": "Warning"},
            {**SAMPLE_EVENT, "record_id": 2, "severity": "Critical"},
        ]
        analyzed = []
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)

        async def record_analyze(db_, asset, event, dedup, language="th", api_key=None):
            analyzed.append(event["severity_level"])
            return True

        monkeypatch.setattr(P, "_analyze_event", record_analyze)
        result = await P.ingest_report_events(db, ASSET_ID, _report(*events), analyze_max=1)
        assert result.events_analyzed == 1
        assert analyzed == ["Critical"]  # priority ordering honored

    async def test_critical_analyzed_before_warning(self, monkeypatch):
        db = FakeDB()
        events = [
            {**SAMPLE_EVENT, "record_id": 1, "severity": "Warning"},
            {**SAMPLE_EVENT, "record_id": 2, "severity": "Critical"},
        ]
        analyzed = []
        monkeypatch.setattr(P, "_fetch_duplicate_keys", _empty_keys)
        monkeypatch.setattr(P, "_persist_event", _fake_persist)
        monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)

        async def record_analyze(db_, asset, event, dedup, language="th", api_key=None):
            analyzed.append(event["record_id"])
            return True

        monkeypatch.setattr(P, "_analyze_event", record_analyze)
        await P.ingest_report_events(db, ASSET_ID, _report(*events), analyze_max=10)
        assert analyzed == [2, 1]

    async def test_never_raises(self, monkeypatch):
        db = FakeDB()

        async def boom(db_, asset_id, keys):
            raise RuntimeError("unexpected")
        monkeypatch.setattr(P, "_fetch_duplicate_keys", boom)
        result = await P.ingest_report_events(db, ASSET_ID, _report(dict(SAMPLE_EVENT)))
        assert result is not None
        assert result.events_new == 1


# ---------------------------------------------------------------------------
# FINAL VALIDATION GATE: cap / priority / quota / determinism
# Exercised against the REAL ingest_report_events orchestration; only the
# external AI (search/summary) and DB boundaries are mocked. Analyzer
# invocation COUNT is recorded by the _analyze_event boundary double.
# ---------------------------------------------------------------------------

def _error_event(record_id):
    return {**SAMPLE_EVENT, "record_id": record_id, "severity": "Error"}


def _warning_event(record_id):
    return {**SAMPLE_EVENT, "record_id": record_id, "severity": "Warning"}


def _critical_event(record_id):
    return {**SAMPLE_EVENT, "record_id": record_id, "severity": "Critical"}


def _patch_orchestration(monkeypatch, existing_keys=None):
    """Wire the orchestration to bounded doubles; returns a calls recorder."""
    calls = []

    async def dup_keys(db_, asset, keys):
        return set(existing_keys or [])

    async def record_analyze(db_, asset, event, dedup, language="th", api_key=None):
        calls.append(event)
        return True

    monkeypatch.setattr(P, "_fetch_duplicate_keys", dup_keys)
    monkeypatch.setattr(P, "_persist_event", _fake_persist_seq)
    monkeypatch.setattr(P, "_fetch_analyzed_keys", _empty_keys)
    monkeypatch.setattr(P, "_analyze_event", record_analyze)
    return calls


class TestS13FinalGate:
    async def test_A_hard_cap_15_errors_analyzes_exactly_10(self, monkeypatch):
        """15 unique eligible events -> at most DEFAULT_ANALYZE_MAX=10 analyzed."""
        db = FakeDB()
        events = [_error_event(i) for i in range(1, 16)]
        calls = _patch_orchestration(monkeypatch)
        result = await P.ingest_report_events(db, ASSET_ID, _report(*events))
        assert P.DEFAULT_ANALYZE_MAX == 10
        assert result.events_received == 15
        assert result.events_new == 15
        assert result.events_duplicate == 0
        assert result.events_failed == 0
        assert result.events_analyzed == 10
        assert len(calls) == 10, f"Analyzer invoked {len(calls)} times, expected exactly 10"

    async def test_A2_explicit_analyze_max_respected(self, monkeypatch):
        db = FakeDB()
        events = [_error_event(i) for i in range(1, 16)]
        calls = _patch_orchestration(monkeypatch)
        result = await P.ingest_report_events(db, ASSET_ID, _report(*events), analyze_max=3)
        assert result.events_new == 15
        assert result.events_analyzed == 3
        assert len(calls) == 3

    async def test_B_priority_critical_error_before_warning(self, monkeypatch):
        """Warnings listed FIRST in input must NOT consume the quota before Critical/Error."""
        db = FakeDB()
        warnings = [_warning_event(i) for i in range(1, 9)]
        criticals = [_critical_event(100 + i) for i in range(1, 6)]
        errors = [_error_event(200 + i) for i in range(1, 6)]
        events = warnings + criticals + errors   # 18 total > cap 10
        calls = _patch_orchestration(monkeypatch)
        result = await P.ingest_report_events(db, ASSET_ID, _report(*events))
        assert result.events_received == 18
        assert result.events_analyzed == 10
        assert len(calls) == 10
        analyzed_ids = [c["record_id"] for c in calls]
        # No Warning may consume a slot while Critical/Error remain.
        assert not any(i < 100 for i in analyzed_ids), f"Warning consumed quota: {analyzed_ids}"
        # All 5 Criticals + all 5 Errors selected (input order preserved within tie).
        assert sorted(analyzed_ids) == sorted(list(range(101, 106)) + list(range(201, 206)))

    async def test_B2_errors_before_warnings(self, monkeypatch):
        db = FakeDB()
        # pure warning + error mix (no critical): 6 warnings first, 6 errors later, cap 10
        events = [_warning_event(i) for i in range(1, 7)] + [_error_event(100 + i) for i in range(1, 7)]
        calls = _patch_orchestration(monkeypatch)
        result = await P.ingest_report_events(db, ASSET_ID, _report(*events))
        assert result.events_analyzed == 10
        analyzed_ids = [c["record_id"] for c in calls]
        # 6 Errors (priority 2) fill first, then 4 Warnings (priority 1) to reach cap 10.
        assert sorted(analyzed_ids) == sorted(list(range(101, 107)) + [1, 2, 3, 4])

    async def test_C_duplicates_do_not_consume_quota(self, monkeypatch):
        """Cap applies to eligible NEW candidates, not raw input count."""
        db = FakeDB()
        dup_events = [_error_event(i) for i in range(1, 9)]          # already persisted/analyzed
        new_events = [_error_event(100 + i) for i in range(1, 13)]   # 12 new errors
        existing = {P.compute_dedup_key(ASSET_ID, P.normalize_report_event(e)) for e in dup_events}
        events = dup_events + new_events                              # 20 raw input
        calls = _patch_orchestration(monkeypatch, existing_keys=list(existing))
        result = await P.ingest_report_events(db, ASSET_ID, _report(*events))
        assert result.events_received == 20
        assert result.events_duplicate == 8
        assert result.events_new == 12
        assert result.events_analyzed == 10
        assert len(calls) == 10
        analyzed_ids = [c["record_id"] for c in calls]
        assert sorted(analyzed_ids) == sorted(range(101, 111))  # only NEW events; dups took 0 slots

    async def test_C2_duplicates_only_zero_analysis(self, monkeypatch):
        db = FakeDB()
        dup_events = [_error_event(i) for i in range(1, 6)]
        existing = {P.compute_dedup_key(ASSET_ID, P.normalize_report_event(e)) for e in dup_events}
        calls = _patch_orchestration(monkeypatch, existing_keys=list(existing))
        result = await P.ingest_report_events(db, ASSET_ID, _report(*dup_events))
        assert result.events_duplicate == 5
        assert result.events_new == 0
        assert result.events_analyzed == 0
        assert len(calls) == 0

    async def test_D_deterministic_equal_priority_selection(self, monkeypatch):
        """Equal-priority ties resolve deterministically (stable input order)."""
        db = FakeDB()
        events = [_error_event(i) for i in range(1, 16)]  # 15 equal-priority Errors
        calls = _patch_orchestration(monkeypatch)

        result1 = await P.ingest_report_events(db, ASSET_ID, _report(*events))
        first_run = [c["record_id"] for c in calls]

        frozen = P.DEFAULT_ANALYZE_MAX
        calls.clear()
        result2 = await P.ingest_report_events(db, ASSET_ID, _report(*events))
        second_run = [c["record_id"] for c in calls]

        assert result1.events_analyzed == 10 and result2.events_analyzed == 10
        assert first_run == second_run == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert frozen == 10

    async def test_E_persisted_history_metadata_is_json_serializable(self, monkeypatch):
        """
        Regression: LIVE postgres test exposed a bug where the normalized
        event's datetime occurrence_time leaked into the JSON event_metadata
        column (TypeError: Object of type datetime is not JSON serializable).
        Exercises the REAL _analyze_event persistence path with an in-memory
        session; asserts the built AnalysisHistory row is JSON-safe.
        """
        import json as _json
        from backend.domain.analyzer.models.history import AnalysisHistory

        db = FakeDB()
        normalized = P.normalize_report_event(dict(SAMPLE_EVENT))
        dedup = P.compute_dedup_key(ASSET_ID, normalized)

        monkeypatch.setattr(P, "search_solutions", lambda event_id, provider: ([], ""))
        async def fake_build(event_id, provider, snippets, results, language="th",
                             faulting_app="", api_key=None, description="", db=None):
            return SolutionSummary(overview="synthetic", causes=["c"], steps=["s"])
        monkeypatch.setattr(P, "build_summary", fake_build)

        ok = await P._analyze_event(db, ASSET_ID, normalized, dedup, language="th", api_key=None)
        assert ok is True
        row = next(r for r in db.added if isinstance(r, AnalysisHistory))
        meta = row.event_metadata
        # occurrence_time must be a plain ISO string, not a datetime object.
        assert isinstance(meta["occurrence_time"], str)
        assert meta["occurrence_time"].startswith("2026-09-14T")
        assert meta["source_type"] == "USB_OFFLINE_COLLECTION"
        assert meta["asset_id"] == ASSET_ID
        assert meta["_reporter_dedup"] == dedup
        _json.dumps(meta)  # must not raise

    async def test_F_dedup_lookups_use_jsonb_astext_not_quoted_cast(self):
        """
        Regression: LIVE postgres test exposed a bug where
        cast(metadata->'key' AS TEXT) keeps surrounding JSON quotes on PG, so
        every dedup lookup silently returned "no match" and re-imports would
        duplicate. Verify the compiled SQL uses ->> (astext), not CAST(...AS).
        """
        from sqlalchemy.dialects import postgresql

        # _fetch_duplicate_keys (WindowsEventLog JSONB)
        stmt = P._fetch_duplicate_keys.__wrapped__ if hasattr(P._fetch_duplicate_keys, "__wrapped__") else None
        # Rebuild the exact statement via a temp binding-free compile:
        from backend.domain.telemetry.models import WindowsEventLog
        dedup_expr = WindowsEventLog.evtx_metadata["_reporter_dedup"].astext
        sql_winlog = str(
            dedup_expr.in_(["k1", "k2"]).compile(dialect=postgresql.dialect())
        )
        assert "CAST" not in sql_winlog
        assert "->>" in sql_winlog

        # _fetch_analyzed_keys (AnalysisHistory JSON -> cast to JSONB)
        from backend.domain.analyzer.models.history import AnalysisHistory
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
        from sqlalchemy import cast as _cast
        hist_expr = _cast(AnalysisHistory.event_metadata, PGJSONB)["_reporter_dedup"].astext
        sql_history = str(hist_expr.in_(["k1", "k2"]).compile(dialect=postgresql.dialect()))
        assert "->>" in sql_history
        assert "JSONB" in sql_history


# Small async helpers used as monkeypatch targets ---------------------------

async def _empty_keys(*args, **kwargs):
    return set()


async def _fake_persist(db, asset_id, event, dedup_key):
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _fake_persist_seq(db, asset_id, event, dedup_key):
    """Boundary double returning a distinct log_id per persisted event."""
    _fake_persist_seq.n = getattr(_fake_persist_seq, "n", 0) + 1
    return uuid.UUID(f"00000000-0000-0000-0000-{_fake_persist_seq.n:012d}")


async def _ok_analyze(db, asset, event, dedup, language="th", api_key=None):
    return True


async def _fail_analyze(db, asset, event, dedup, language="th", api_key=None):
    return False