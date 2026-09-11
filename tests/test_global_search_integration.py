"""
==============================================================================
EIMS Automated Integration Test Suite — Global Search Engine & Real DB Providers
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 3 & 4 Compliance
==============================================================================
Proves real database provider execution against live PostgreSQL instance:
- Exact match, prefix match, partial match, case-insensitive search, numeric search
- Navigation provider route resolution
- Multi-provider aggregation & isolation upon provider exceptions
- Deep-link contextual destination URLs
- Strict transaction rollback isolation (Zero TRUNCATE, Zero DB pollution)
"""

import uuid
import pytest
from datetime import datetime, timezone

from backend.infrastructure.database import database_engine
from backend.domain.asset_registry.models import InfrastructureAsset, AuditLog, OCRRegistrationRecord
from backend.domain.telemetry.models import WindowsEventLog, TelemetryMetric
from backend.domain.evaluation.models import ServiceSession
from backend.domain.search.service import GlobalSearchService
from backend.domain.search.providers import (
    NavigationSearchProvider,
    AssetSearchProvider,
    AuditLogSearchProvider,
    WindowsEventLogSearchProvider,
    UsbAuditorSearchProvider,
    OcrSearchProvider,
    TelemetrySearchProvider,
    EvaluationSearchProvider,
    AnalysisSearchProvider,
)
from backend.domain.search.provider import SearchProvider, SearchResult


from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.core.config import settings


@pytest.fixture
async def db_session():
    """Provides an isolated AsyncSession per test on that test's event loop."""
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"prepared_statement_cache_size": 0},
    )
    sm = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    async with sm() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_navigation_search_provider_routes():
    """Verifies static navigation provider resolves key operational pages without DB dependency."""
    nav_provider = NavigationSearchProvider()

    # Test conceptual route searches
    queries_to_expected = {
        "timeline": "/timeline",
        "analyzer": "/analyzer",
        "usb": "/endpoints",
        "ocr": "/ocr-history",
        "endpoint": "/endpoints",
        "evaluation": "/evaluations",
        "observability": "/observability",
        "dashboard": "/",
    }

    for query, expected_dest in queries_to_expected.items():
        results = await nav_provider.search(None, query, limit=5)
        assert len(results) > 0, f"Navigation provider failed to resolve query: '{query}'"
        assert any(expected_dest == r.url or expected_dest in r.url for r in results), (
            f"Query '{query}' did not produce destination '{expected_dest}'. Got: {[r.url for r in results]}"
        )
        for r in results:
            assert r.result_kind == "navigation"
            assert r.type == "navigation"


@pytest.mark.asyncio
async def test_asset_and_usb_search_provider_real_db(db_session: AsyncSession):
    """Tests AssetSearchProvider and UsbAuditorSearchProvider against real DB with rollback."""
    async with db_session.begin() as trans:
        # Seed test asset with USB evidence in offline_report_data
        test_asset_id = uuid.uuid4()
        test_fingerprint = f"test_fp_{uuid.uuid4().hex[:16]}"
        asset = InfrastructureAsset(
            asset_id=test_asset_id,
            hostname="KEL-PROD-WEB-TEST-99",
            canonical_ip="10.240.99.10",
            cryptographic_fingerprint=test_fingerprint,
            lifecycle_state="Discovered",
            current_compliance_score=85,
            offline_report_data={
                "usb_devices": [
                    {"device_name": "UltraFast Kingston Flash Drive", "serial_number": "KINGSTON-XYZ-9988"}
                ]
            },
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(asset)
        await db_session.flush()

        asset_provider = AssetSearchProvider()
        usb_provider = UsbAuditorSearchProvider()

        # 1. Exact match hostname
        results = await asset_provider.search(db_session, "KEL-PROD-WEB-TEST-99", limit=10)
        assert len(results) >= 1
        assert results[0].id == str(test_asset_id)
        assert results[0].result_kind == "entity"
        assert results[0].url == f"/endpoints?id={test_asset_id}"

        # 2. Case-insensitive prefix/partial match
        results_lower = await asset_provider.search(db_session, "kel-prod-web", limit=10)
        assert any(r.id == str(test_asset_id) for r in results_lower)

        # 3. Cryptographic fingerprint search
        results_fp = await asset_provider.search(db_session, test_fingerprint[:10], limit=10)
        assert any(r.id == str(test_asset_id) for r in results_fp)

        # 4. USB Auditor Search Provider (finding asset via USB serial / device name)
        usb_results = await usb_provider.search(db_session, "KINGSTON-XYZ", limit=10)
        assert len(usb_results) >= 1
        assert usb_results[0].id == str(test_asset_id)
        assert usb_results[0].type == "usb"
        assert usb_results[0].url == f"/endpoints?id={test_asset_id}"

        # Rollback transaction cleanly
        await trans.rollback()


@pytest.mark.asyncio
async def test_windows_event_log_search_provider_real_db(db_session: AsyncSession):
    """Tests WindowsEventLogSearchProvider with numeric search (4625) and text metadata."""
    async with db_session.begin() as trans:
        # Seed asset and associated winlog
        test_asset_id = uuid.uuid4()
        asset = InfrastructureAsset(
            asset_id=test_asset_id,
            hostname="KEL-SEC-WIN-01",
            canonical_ip="10.240.1.200",
            cryptographic_fingerprint=f"win_fp_{uuid.uuid4().hex[:16]}",
            lifecycle_state="Commissioned",
            current_compliance_score=90,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(asset)
        await db_session.flush()

        winlog = WindowsEventLog(
            asset_id=test_asset_id,
            event_id=4625,
            severity_level="Critical",
            occurrence_time=datetime.now(timezone.utc),
            evtx_metadata={"event_channel": "Security", "target_user_name": "compromised_admin", "reason": "Unknown user name or bad password"}
        )
        db_session.add(winlog)
        await db_session.flush()

        winlog_provider = WindowsEventLogSearchProvider()

        # 1. Numeric search: 4625
        results = await winlog_provider.search(db_session, "4625", limit=10)
        assert len(results) >= 1
        matching = [r for r in results if r.id == str(winlog.log_id)]
        assert len(matching) == 1
        assert matching[0].type == "winlog"
        assert matching[0].result_kind == "entity"
        assert matching[0].url == f"/timeline?type=winlog&entity_id={test_asset_id}"
        assert "KEL-SEC-WIN-01" in matching[0].subtitle

        # 2. Text metadata search: "compromised_admin"
        text_results = await winlog_provider.search(db_session, "compromised_admin", limit=10)
        assert any(r.id == str(winlog.log_id) for r in text_results)

        # 3. Severity search: "Critical"
        crit_results = await winlog_provider.search(db_session, "Critical", limit=10)
        assert any(r.id == str(winlog.log_id) for r in crit_results)

        await trans.rollback()


@pytest.mark.asyncio
async def test_ocr_search_provider_real_db(db_session: AsyncSession):
    """Tests OcrSearchProvider parsing sticker text in OCRRegistrationRecord."""
    async with db_session.begin() as trans:
        record_id = uuid.uuid4()
        ocr_record = OCRRegistrationRecord(
            record_id=record_id,
            minio_object_uri="minio://ocr-bucket/sticker-99.jpg",
            extraction_status="Completed",
            parsed_raw_text={
                "detected_serial": "DELL-SRV-OCR-887766",
                "mac_address": "00:1A:2B:3C:4D:5E",
                "model": "PowerEdge R740"
            }
        )
        db_session.add(ocr_record)
        await db_session.flush()

        ocr_provider = OcrSearchProvider()

        # Search by serial number inside JSON
        results = await ocr_provider.search(db_session, "DELL-SRV-OCR", limit=10)
        assert len(results) >= 1
        match = next((r for r in results if r.id == str(record_id)), None)
        assert match is not None
        assert match.type == "ocr"
        assert match.result_kind == "entity"
        assert match.url == "/ocr-history"

        # Search by MAC address
        mac_results = await ocr_provider.search(db_session, "00:1A:2B", limit=10)
        assert any(r.id == str(record_id) for r in mac_results)

        await trans.rollback()


@pytest.mark.asyncio
async def test_audit_log_search_provider_real_db(db_session: AsyncSession):
    """Tests AuditLogSearchProvider with immutable_payload and event_type matching."""
    async with db_session.begin() as trans:
        test_asset_id = uuid.uuid4()
        asset = InfrastructureAsset(
            asset_id=test_asset_id,
            hostname="KEL-AUDIT-NODE-01",
            canonical_ip="10.240.3.11",
            cryptographic_fingerprint=f"audit_fp_{uuid.uuid4().hex[:16]}",
            lifecycle_state="Commissioned",
            current_compliance_score=92,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(asset)
        await db_session.flush()

        log_id = uuid.uuid4()
        audit_log = AuditLog(
            log_id=log_id,
            action_verb="AUTH_FAILURE",
            asset_id=test_asset_id,
            immutable_payload={"reason": "brute_force_detected", "source_ip": "192.168.100.50"},
            actor_id=uuid.uuid4(),
            performed_at=datetime.now(timezone.utc)
        )
        db_session.add(audit_log)
        await db_session.flush()

        audit_provider = AuditLogSearchProvider()

        # 1. Search by action_verb
        results = await audit_provider.search(db_session, "AUTH_FAILURE", limit=10)
        assert any(r.id == str(log_id) for r in results)

        # 2. Search by payload content: "brute_force"
        bf_results = await audit_provider.search(db_session, "brute_force", limit=10)
        assert any(r.id == str(log_id) for r in bf_results)
        match = next(r for r in bf_results if r.id == str(log_id))
        assert match.type == "audit"
        assert match.result_kind == "entity"
        assert match.url == f"/timeline?type=audit&entity_id={test_asset_id}"

        await trans.rollback()


@pytest.mark.asyncio
async def test_telemetry_search_provider_contextual_guard(db_session: AsyncSession):
    """Tests TelemetrySearchProvider respects anomaly/vital throttling and doesn't dump all rows."""
    async with db_session.begin() as trans:
        test_asset_id = uuid.uuid4()
        asset = InfrastructureAsset(
            asset_id=test_asset_id,
            hostname="KEL-GPU-NODE-01",
            canonical_ip="10.240.2.55",
            cryptographic_fingerprint=f"gpu_fp_{uuid.uuid4().hex[:16]}",
            lifecycle_state="Commissioned",
            current_compliance_score=95,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(asset)
        await db_session.flush()

        # Add anomaly metric with high GPU load in diagnostic_payload
        metric = TelemetryMetric(
            asset_id=test_asset_id,
            cpu_utilization=98.5,
            diagnostic_payload={"gpu_utilization": 99.2, "temp_c": 88, "alert": "GPU Overheating Warning"},
            event_time=datetime.now(timezone.utc)
        )
        db_session.add(metric)
        await db_session.flush()

        telemetry_provider = TelemetrySearchProvider()

        # Search "gpu"
        gpu_results = await telemetry_provider.search(db_session, "gpu", limit=5)
        assert len(gpu_results) <= 5
        matching = [r for r in gpu_results if r.metadata.get("asset_id") == str(test_asset_id)]
        assert len(matching) >= 1
        assert matching[0].type == "telemetry"
        assert matching[0].result_kind == "entity"
        assert "observability" in matching[0].url

        await trans.rollback()


from backend.domain.search.registry import SearchProviderRegistry

@pytest.mark.asyncio
async def test_multi_provider_aggregation_and_failure_isolation(db_session: AsyncSession):
    """Tests GlobalSearchService aggregates from all providers and gracefully isolates buggy providers."""
    class BrokenSearchProvider(SearchProvider):
        name = "broken_mock"

        async def search(self, db, query: str, limit: int = 10):
            raise RuntimeError("Deliberate simulated hardware or network socket failure!")

    registry = SearchProviderRegistry()
    registry.register(NavigationSearchProvider())
    registry.register(BrokenSearchProvider())
    service = GlobalSearchService(registry=registry)

    # Search should NOT throw, and should return navigation results despite BrokenSearchProvider crashing
    results, count = await service.global_search(db=db_session, query="timeline", search_type=None, limit=10)
    assert len(results) > 0
    assert count > 0
    assert any(r.result_kind == "navigation" for r in results)
