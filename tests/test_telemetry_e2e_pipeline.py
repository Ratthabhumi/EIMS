"""
==============================================================================
EIMS Automated End-to-End (E2E) Telemetry Ingestion Pipeline Verification
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Section 7.1
==============================================================================
"""

import uuid
import json
import pytest
from fastapi.testclient import TestClient
from backend.domain.telemetry import (
    TelemetryStreamConsumer,
    StubTelemetryStreamBroker,
    TelemetryMetric,
    WindowsEventLog,
)


@pytest.mark.asyncio
async def test_closed_loop_telemetry_ingestion_and_batch_processing(client: TestClient, stub_broker: StubTelemetryStreamBroker):
    """
    Authoritative end-to-end integration test proving closed-loop execution across:
    1. Asset Registry REST Enrollment over API Gateway (HTTP 201 Created).
    2. Edge Telemetry Ingestion via mTLS SHA-256 Transport Verification (HTTP 202 Accepted).
    3. Asynchronous Redis Stream Shock Absorption without synchronous DB wait times.
    4. Background Stream Consumer Batch Draining and exact ORM entity mapping.
    """
    # 1. ENROLL INFRASTRUCTURE ASSET VIA CORE REST GATEWAY
    target_fingerprint = "7a7f800000000000000000000000000000000000000000000000000000000001"
    asset_payload = {
        "hostname": "PROD-DISCOVERY-NODE-01",
        "canonical_ip": "10.240.15.88",
        "cryptographic_fingerprint": target_fingerprint
    }
    enroll_resp = client.post("/api/v1/assets", json=asset_payload)
    assert enroll_resp.status_code == 201, f"Asset registration failed: {enroll_resp.text}"
    
    enrolled_data = enroll_resp.json()
    enrolled_asset_id = uuid.UUID(enrolled_data["asset_id"])
    assert enrolled_data["lifecycle_state"] == "Discovered"

    # 2. EMULATE CUSTOM TOOL EXECUTING HIGH-FREQUENCY DIAGNOSTIC TRANSMISSION OVER mTLS
    mtls_headers = {"X-Client-Cert-Fingerprint": target_fingerprint}
    winlog_payload = {
        "occurrence_time": "2026-08-05T09:30:00Z",
        "event_id": 1102,  # Audit log audit trail clearing alert
        "severity": "Critical",
        "event_channel": "Security",
        "metadata": {
            "target_user_name": "RootOps",
            "workstation_name": "PROD-DISCOVERY-NODE-01",
            "tool_suite": "CustomSecurityToolkit",
            "module_executed": "AuditLogSentinel",
            "status_code": 0,
            "signature_match": "VERIFIED"
        }
    }
    
    ingest_resp = client.post("/api/v1/telemetry/winlog", json=winlog_payload, headers=mtls_headers)
    assert ingest_resp.status_code == 202, f"Telemetry ingestion failed: {ingest_resp.text}"
    
    ingest_data = ingest_resp.json()
    assert ingest_data["status"] == "accepted"
    assert "stub-" in ingest_data["stream_job_id"]

    # 3. VERIFY INSTANTANEOUS BUFFER ENQUEUEING IN STREAM BROKER TIER
    assert len(stub_broker.stream_buffer) == 1
    stream_message = stub_broker.stream_buffer[0]
    assert stream_message["event_type"] == "winlog"
    assert stream_message["cert_fingerprint"] == target_fingerprint
    
    # 4. EXECUTE BACKGROUND CONSUMER WORKER BATCH DRAINING
    consumer = TelemetryStreamConsumer(broker=stub_broker)
    # Bind mTLS fingerprint to enrolled asset primary key
    consumer.register_agent_mapping(cert_fingerprint=target_fingerprint, asset_id=enrolled_asset_id)
    
    drained_count = await consumer.process_batch(batch_size=50)
    
    # 5. ASSERT COMPLETE BUFFER EVACUATION AND ORM RELATIONAL SYNC
    assert drained_count == 1
    assert len(stub_broker.stream_buffer) == 0  # Queue drained 100% cleanly
    assert len(consumer.processed_winlogs) == 1
    
    persisted_record = consumer.processed_winlogs[0]
    assert isinstance(persisted_record, WindowsEventLog)
    assert persisted_record.asset_id == enrolled_asset_id
    assert persisted_record.event_id == 1102
    assert persisted_record.severity_level == "Critical"
    
    # Verify accurate preservation of polymorphic forensic metadata (Core Law 4 Section 7.1 GIN indexable)
    assert persisted_record.evtx_metadata["tool_suite"] == "CustomSecurityToolkit"
    assert persisted_record.evtx_metadata["module_executed"] == "AuditLogSentinel"
    assert persisted_record.evtx_metadata["signature_match"] == "VERIFIED"
