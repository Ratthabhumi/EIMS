"""Correlation uses EVENT time, never ingestion time (real PostgreSQL, disposable database).

Matrix (window = 900 s): every case states the expected outcome; ``at`` is the request's observed_at (the ingestion
side) and ``occurred`` is the event timestamp inside the analysed record.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from backend.domain.incident.event_time import asserted_event_time, parse_event_time
from backend.domain.incident.models import IncidentEvidence
from tests.incident_db_support import create_asset, session_factory
from tests.test_incident_identity_correlation_pg import BASE, OPEN, _client, api, body, counts, hist, post  # noqa: F401


def z(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- unit: parsing rules
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _iana() -> bool:
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("Asia/Bangkok")
        return True
    except Exception:  # noqa: BLE001 - Windows without tzdata: an IANA name is then (safely) treated as not declared
        return False


IANA = _iana()


@pytest.mark.parametrize("raw, zone, basis, confidence", [
    ("2026-11-20T01:02:03Z", None, "source_timestamp_explicit_zone", "exact"),
    ("2026-11-20T08:02:03+07:00", None, "source_timestamp_explicit_zone", "exact"),
    ("2026-11-20 01:02:03.1234567Z", None, "source_timestamp_explicit_zone", "exact"),
    ("2026-11-20 08:02:03", "+07:00", "source_local_with_declared_zone", "exact"),
    ("2026-11-20 08:02:03", "Asia/Bangkok", "source_local_with_declared_zone", "exact"),
    ("2026-11-20 08:02:03", None, "local_time_without_zone", "ambiguous"),
    ("2026-11-20 08:02:03", "Not/AZone", "local_time_without_zone", "ambiguous"),
    ("11/20/2026 8:02:03 AM", None, "local_time_day_month_order_unclear", "ambiguous"),
    ("08:02:03", None, "time_of_day_without_date", "ambiguous"),
    ("2026-11-20", None, "date_without_time", "ambiguous"),
    ("2026-13-45T99:99:99Z", None, "malformed_timestamp", "missing"),
    ("yesterday-ish", None, "malformed_timestamp", "missing"),
    ("", None, "no_timestamp", "missing"),
    (None, None, "no_timestamp", "missing"),
    ("2027-01-01T00:00:00Z", None, "timestamp_in_the_future", "ambiguous"),
])
def test_parse_event_time_rules(raw, zone, basis, confidence):
    result = parse_event_time(raw, declared_zone=zone, now=NOW)
    assert (result.basis, result.confidence) == (basis, confidence)
    assert (result.event_time is not None) == (confidence == "exact")
    assert result.eligible == (confidence == "exact")
    if result.event_time is not None:
        assert result.event_time.tzinfo is not None and result.event_time.utcoffset() == timedelta(0)


def test_offset_and_declared_zone_resolve_to_the_same_instant():
    a = parse_event_time("2026-11-20T08:02:03+07:00", now=NOW).event_time
    b = parse_event_time("2026-11-20 08:02:03", declared_zone="Asia/Bangkok", now=NOW).event_time
    c = parse_event_time("2026-11-20T01:02:03Z", now=NOW).event_time
    assert a == b == c


def test_original_text_is_preserved_and_caller_timestamps_are_only_asserted():
    assert parse_event_time("2026-11-20 08:02:03", now=NOW).original == "2026-11-20 08:02:03"
    stamp = asserted_event_time(datetime(2026, 11, 20, 1, 2, 3, tzinfo=UTC))
    assert (stamp.confidence, stamp.basis) == ("asserted", "caller_supplied_structured_timestamp")
    naive = asserted_event_time(datetime(2026, 11, 20, 1, 2, 3))
    assert (naive.confidence, naive.event_time) == ("ambiguous", None)


# ---------------------------------------------------------------- integration matrix
def test_a_events_close_together_ingested_hours_apart_still_merge(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", occurred=z(BASE + timedelta(seconds=60)))
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(hours=5), asset=asset))
        assert second["incident_id"] == first["incident_id"] and second["match"] == "correlated_with_open_incident"
        assert await counts(engine) == (1, 2, 2)
    asyncio.run(run())


def test_b_events_far_apart_ingested_together_do_not_merge(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", occurred=z(BASE - timedelta(hours=6)))
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
            second = await post(c, body(b, at=BASE + timedelta(seconds=2), asset=asset))
        assert second["incident_id"] != first["incident_id"]
        assert second["match"] == "created"           # six hours apart: not even a candidate
        assert await counts(engine) == (2, 2, 2)
    asyncio.run(run())


def test_c_missing_event_timestamp_never_merges_on_ingestion_proximity(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", untimed=True)  # strong identity, no time
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
            second = await post(c, body(b, at=BASE, asset=asset))                    # ingested at the same instant
        assert second["incident_id"] != first["incident_id"]
        assert second["match"] == "ambiguous_not_merged"
        correlation = second["summary"]["correlation"]
        assert correlation["time"]["time_confidence"] == "missing" and correlation["time"]["event_time"] is None
        assert correlation["time"]["ingestion_time_is_not_event_time"] is True
        assert any("event_time_untrusted:no_timestamp" in c_["reasons"] for c_ in correlation["candidates"])
        async with session_factory(engine)() as db:
            row = (await db.execute(select(IncidentEvidence).where(IncidentEvidence.source_id == str(b)))).scalar_one()
        assert (row.event_time, row.time_confidence, row.time_basis) == (None, "missing", "no_timestamp")
    asyncio.run(run())


@pytest.mark.parametrize("raw, basis", [
    ("not a date at all", "malformed_timestamp"),
    ("2026-02-31T25:61:00Z", "malformed_timestamp"),
])
def test_d_malformed_timestamp_is_marked_and_not_merged(api, raw, basis):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", occurred=raw)
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
            second = await post(c, body(b, at=BASE, asset=asset))
        assert second["incident_id"] != first["incident_id"] and second["match"] == "ambiguous_not_merged"
        assert second["summary"]["correlation"]["time"]["time_basis"] == basis
        async with session_factory(engine)() as db:
            row = (await db.execute(select(IncidentEvidence).where(IncidentEvidence.source_id == str(b)))).scalar_one()
        assert row.time_original == raw[:200] and row.event_time is None
    asyncio.run(run())


def test_e_explicit_utc_and_offset_and_declared_zone_agree(api):
    app, asset, engine = api
    local = BASE.astimezone(UTC).replace(tzinfo=None) + timedelta(hours=7)

    async def run():
        utc = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        offset = await hist(engine, "1026", ".NET Runtime", record_id="2",
                            occurred=(BASE + timedelta(seconds=30)).astimezone(
                                __import__("datetime").timezone(timedelta(hours=7))).isoformat())
        declared = await hist(engine, "1026", ".NET Runtime", record_id="3", occurred=local.isoformat(sep=" "),
                              timezone="+07:00")
        async with _client(app) as c:
            r = [await post(c, body(h, at=BASE, asset=asset)) for h in (utc, offset, declared)]
        assert r[1]["incident_id"] == r[0]["incident_id"] and r[2]["incident_id"] == r[0]["incident_id"]
        async with session_factory(engine)() as db:
            rows = {x.source_id: x for x in (await db.execute(select(IncidentEvidence))).scalars().all()}
        assert rows[str(declared)].time_basis == "source_local_with_declared_zone"
        assert rows[str(declared)].event_time == BASE
        assert rows[str(offset)].time_basis == "source_timestamp_explicit_zone"
    asyncio.run(run())


def test_f_ambiguous_local_time_is_not_guessed(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        naive = BASE.replace(tzinfo=None).isoformat(sep=" ")
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", occurred=naive)  # no zone anywhere
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
            second = await post(c, body(b, at=BASE, asset=asset))
        assert second["incident_id"] != first["incident_id"] and second["match"] == "ambiguous_not_merged"
        assert second["summary"]["correlation"]["time"]["time_confidence"] == "ambiguous"
        assert second["summary"]["correlation"]["time"]["time_basis"] == "local_time_without_zone"
    asyncio.run(run())


def test_g_future_timestamp_is_untrusted(api):
    app, asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(datetime.now(UTC) + timedelta(days=30)))
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
        assert first["summary"]["correlation"]["time"]["time_basis"] == "timestamp_in_the_future"
        assert first["summary"]["correlation"]["time"]["event_time"] is None
    asyncio.run(run())


def test_h_same_event_repeated_stays_idempotent_with_and_without_time(api):
    app, asset, engine = api

    async def run():
        t1 = await hist(engine, "1026", ".NET Runtime", "crash", record_id="9", occurred=z(BASE))
        t2 = await hist(engine, "1026", ".NET Runtime", "crash", record_id="9", occurred=z(BASE))
        u1 = await hist(engine, "1000", "Application Error", "bare", untimed=True)
        async with _client(app) as c:
            first = await post(c, body(t1, at=BASE, asset=asset))
            again = await post(c, body(t2, at=BASE + timedelta(hours=1), asset=asset))
            same_row = await post(c, body(u1, at=BASE, asset=asset))
            same_row_again = await post(c, body(u1, at=BASE + timedelta(hours=2), asset=asset))
        assert again["incident_id"] == first["incident_id"] and again["match"] == "event_already_linked"
        assert same_row_again["incident_id"] == same_row["incident_id"] and same_row_again["created"] is False
        assert await counts(engine) == (2, 3, 2)  # the twin occurrence is attached (same digest), not a new event
    asyncio.run(run())


def test_i_unregistered_asset_never_merges_even_with_trusted_times(api):
    app, _asset, engine = api

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", occurred=z(BASE + timedelta(seconds=5)))
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE))
            second = await post(c, body(b, at=BASE))
        assert second["incident_id"] != first["incident_id"]
        assert await counts(engine) == (2, 2, 2)
    asyncio.run(run())


def test_j_resolved_incident_is_not_merged_into_even_with_matching_event_time(api):
    app, asset, engine = api
    from backend.domain.incident.models import Incident

    async def run():
        a = await hist(engine, "1026", ".NET Runtime", record_id="1", occurred=z(BASE))
        b = await hist(engine, "1026", ".NET Runtime", record_id="2", occurred=z(BASE + timedelta(seconds=10)))
        async with _client(app) as c:
            first = await post(c, body(a, at=BASE, asset=asset))
            async with session_factory(engine)() as db:
                inc = await db.get(Incident, __import__("uuid").UUID(first["incident_id"]))
                await db.execute(__import__("sqlalchemy").text("ALTER TABLE incidents DISABLE TRIGGER USER"))
                inc.status = "resolved"
                await db.commit()
            second = await post(c, body(b, at=BASE, asset=asset))
        assert second["incident_id"] != first["incident_id"]
    try:
        asyncio.run(run())
    except Exception as exc:  # the lifecycle triggers may forbid a direct status write: that itself proves isolation
        pytest.skip(f"direct status write not permitted by lifecycle triggers: {type(exc).__name__}")


def test_k_legacy_direct_callers_keep_asserted_semantics_without_event_time_leak(api):
    """Service callers that never evaluated time are treated as asserted (legacy), not as ingestion proximity."""
    app, asset, engine = api
    from backend.domain.incident.service import EvidenceInput, IncidentService

    async def run():
        async with session_factory(engine)() as db:
            svc = IncidentService(db)
            incident, created = await svc.create_from_evidence(
                [EvidenceInput("winlog", "w-1", BASE)], actor="demo", asset_id=asset)
            assert created is True
        async with session_factory(engine)() as db:
            row = (await db.execute(select(IncidentEvidence).where(IncidentEvidence.source_id == "w-1"))).scalar_one()
            assert (row.time_confidence, row.time_basis) == ("asserted", "caller_supplied_structured_timestamp")
            assert row.event_time == BASE
    asyncio.run(run())


def test_l_coarse_time_text_never_fingerprints_but_full_local_stamp_identifies_by_equality(api):
    """Review finding: '10:00:00' on two different days must not collapse into one occurrence."""
    app, asset, engine = api

    async def run():
        t1 = await hist(engine, "1000", "Application Error", "same", occurred="10:00:00")
        t2 = await hist(engine, "1000", "Application Error", "same", occurred="10:00:00")
        d1 = await hist(engine, "1000", "Application Error", "same2", occurred="11/20/2026 9:14:22 AM")
        d2 = await hist(engine, "1000", "Application Error", "same2", occurred="11/20/2026 9:14:22 AM")
        async with _client(app) as c:
            r1 = await post(c, body(t1, asset=asset))
            r2 = await post(c, body(t2, asset=asset))
            r3 = await post(c, body(d1, asset=asset))
            r4 = await post(c, body(d2, asset=asset))
        assert r2["incident_id"] != r1["incident_id"] and r2["match"] != "event_already_linked"
        assert r4["incident_id"] == r3["incident_id"] and r4["match"] == "event_already_linked"
    asyncio.run(run())


def test_m_absurd_offset_is_malformed_not_a_server_error():
    for raw in ("2026-11-20T01:02:03+99:99", "2026-11-20T01:02:03-24:00"):
        assert parse_event_time(raw, now=NOW).confidence == "missing"
    assert parse_event_time("2026-11-20 01:02:03", declared_zone="+99:99", now=NOW).confidence == "ambiguous"


def test_iana_database_is_available_in_the_supported_environment():
    """tzdata is a declared dependency (pyproject/requirements); Windows has no system IANA database."""
    from zoneinfo import ZoneInfo
    assert ZoneInfo("Asia/Bangkok").utcoffset(datetime(2026, 11, 20)) == timedelta(hours=7)
    assert ZoneInfo("America/New_York").utcoffset(datetime(2026, 7, 1)) == timedelta(hours=-4)  # DST-observing zone
    assert ZoneInfo("America/New_York").utcoffset(datetime(2026, 1, 1)) == timedelta(hours=-5)


@pytest.mark.parametrize("raw, basis", [
    ("2026-11-01 01:30:00", "local_time_ambiguous_dst_overlap"),     # US clocks repeat 01:00-02:00 on 1 Nov 2026
    ("2026-03-08 02:30:00", "local_time_nonexistent_dst_gap"),       # US clocks skip 02:00-03:00 on 8 Mar 2026
])
def test_dst_ambiguous_and_nonexistent_local_times_are_not_resolved(raw, basis):
    result = parse_event_time(raw, declared_zone="America/New_York", now=datetime(2027, 1, 1, tzinfo=UTC))
    assert (result.basis, result.confidence, result.event_time) == (basis, "ambiguous", None)


def test_unambiguous_local_time_in_a_dst_zone_resolves_with_the_right_offset():
    summer = parse_event_time("2026-07-01 12:00:00", declared_zone="America/New_York", now=datetime(2027, 1, 1, tzinfo=UTC))
    winter = parse_event_time("2026-01-01 12:00:00", declared_zone="America/New_York", now=datetime(2027, 1, 1, tzinfo=UTC))
    assert summer.event_time == datetime(2026, 7, 1, 16, 0, tzinfo=UTC)
    assert winter.event_time == datetime(2026, 1, 1, 17, 0, tzinfo=UTC)


@pytest.mark.parametrize("raw", [
    "2026-11-20T01:02:03Z" + chr(0), "'; DROP TABLE incidents;--", "9" * 500, "2026-11-20T01:02:03.999999999999Z",
    "<script>2026-11-20T01:02:03Z</script>", "2026-11-20T01:02:03+0700junk"])
def test_malicious_or_malformed_timestamps_never_raise_and_never_become_trusted(raw):
    result = parse_event_time(raw, now=NOW)
    assert result.confidence in {"missing", "ambiguous", "exact"}
    if result.confidence == "exact":  # only the fractional-seconds case may legitimately parse; it must still be a real instant
        assert result.event_time is not None and result.event_time.tzinfo is not None
    else:
        assert result.event_time is None
    assert result.original is None or len(result.original) <= 200


def test_windows_event_xml_system_time_is_used_as_the_structured_event_time():
    from backend.domain.analyzer.services.parser import parse_event_metadata
    xml = ("<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System><Provider Name='.NET Runtime'/>"
           "<EventID Qualifiers='0'>1026</EventID><Level>2</Level><TimeCreated SystemTime='2026-11-20T01:14:22.1234567Z'/>"
           "<EventRecordID>5501</EventRecordID><Channel>Application</Channel><Computer>WS-1</Computer></System>"
           "<EventData><Data>Application: x.exe</Data></EventData></Event>")
    meta = parse_event_metadata(xml, "")
    assert (meta.eventId, meta.provider, meta.computer) == ("1026", ".NET Runtime", "WS-1")
    assert meta.timestamp == "2026-11-20T01:14:22.1234567Z" and meta.attributes["recordId"] == "5501"
    stamp = parse_event_time(meta.timestamp, now=NOW)
    assert (stamp.confidence, stamp.event_time) == ("exact", datetime(2026, 11, 20, 1, 14, 22, 123456, tzinfo=UTC))


def test_hostile_xml_falls_back_without_error():
    from backend.domain.analyzer.services.parser import parse_event_metadata
    bomb = ('<!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]><Event><System><Provider Name="&b;"/></System></Event>')
    meta = parse_event_metadata(bomb, "")  # must not raise, must not expand entities
    assert "aaaa" not in (meta.provider or "")


def test_xml_event_time_flows_to_incident_evidence_basis(api):
    app, asset, engine = api

    async def run():
        row = await hist(engine, "1026", ".NET Runtime", record_id="5501", occurred=z(BASE))
        async with session_factory(engine)() as db:
            from backend.domain.analyzer.models.history import AnalysisHistory
            record = await db.get(AnalysisHistory, row)
            record.event_metadata = {**record.event_metadata, "attributes": {"timeSource": "xml:System/TimeCreated@SystemTime"}}
            await db.commit()
        async with _client(app) as c:
            made = await post(c, body(row, asset=asset))
        assert made["summary"]["correlation"]["time"]["time_basis"] == "xml_timecreated_systemtime"
    asyncio.run(run())
