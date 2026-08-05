"""
==============================================================================
EIMS Automated Test Suite — Telemetry Background Consumer Worker & ORM Models
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Compliance
==============================================================================
"""

import uuid
import pytest
from datetime import datetime, timezone
from backend.domain.telemetry import (
    TelemetryMetric,
    WindowsEventLog,
    StubTelemetryStreamBroker,
    TelemetryStreamConsumer,
    HeartbeatMetrics,
    AgentHeartbeatRequest,
    WinlogMetadata,
    AgentWinlogRequest,
)


def test_telemetry_orm_table_and_index_metadata():
    """Verifies table mapping structures, composite time index, and JSONB GIN index definitions."""
    metric_indexes = {idx.name: idx for idx in TelemetryMetric.__table__.indexes}
    assert "idx_telemetry_asset_time" in metric_indexes
    assert TelemetryMetric.__tablename__ == "telemetry_metrics"
    
    winlog_indexes = {idx.name: idx for idx in WindowsEventLog.__table__.indexes}
    assert "idx_winlog_metadata_gin" in winlog_indexes
    assert winlog_indexes["idx_winlog_metadata_gin"].dialect_options["postgresql"]["using"] == "gin"
    assert WindowsEventLog.__tablename__ == "windows_event_logs"


@pytest.mark.asyncio
async def test_stream_consumer_batch_draining_and_asset_resolution():
    """Proves worker daemon drains stream queues in configurable batch chunks and maps mTLS identity."""
    stub_broker = StubTelemetryStreamBroker()
    consumer = TelemetryStreamConsumer(broker=stub_broker)
    
    # Pre-register verified agent certificate hash to specific asset UUID
    test_asset_id = uuid.uuid4()
    agent_hash = "f" * 64
    consumer.register_agent_mapping(cert_fingerprint=agent_hash, asset_id=test_asset_id)
    
    # Simulate high-frequency ingestion burst: 15 Heartbeats + 10 Winlogs
    for i in range(15):
        hb = AgentHeartbeatRequest(
            agent_version="v2.0.0",
            timestamp=datetime.now(timezone.utc),
            metrics=HeartbeatMetrics(cpu_utilization=30.0 + i, ram_used_mb=4096, ram_total_mb=16384, disk_iops=100)
        )
        await stub_broker.publish_heartbeat(hb, cert_fingerprint=agent_hash)
        
    for j in range(10):
        wl = AgentWinlogRequest(
            occurrence_time=datetime.now(timezone.utc),
            event_id=4624,
            severity="Information",
            event_channel="Security",
            metadata=WinlogMetadata(workstation_name=f"PC-{j}", event_source="DiskDeleter")
        )
        await stub_broker.publish_winlog(wl, cert_fingerprint=agent_hash)
        
    assert len(stub_broker.stream_buffer) == 25
    
    # Process partial batch chunk of 15
    processed_1 = await consumer.process_batch(batch_size=15)
    assert processed_1 == 15
    assert len(stub_broker.stream_buffer) == 10  # Remaining items waiting for next drain
    assert len(consumer.processed_metrics) == 15
    assert len(consumer.processed_winlogs) == 0
    
    # Verify asset binding identity on processed metric record
    assert consumer.processed_metrics[0].asset_id == test_asset_id
    assert consumer.processed_metrics[0].cpu_utilization == 30.0
    assert consumer.processed_metrics[0].diagnostic_payload["disk_iops"] == 100

    # Process remaining batch chunk
    processed_2 = await consumer.process_batch(batch_size=20)
    assert processed_2 == 10
    assert len(stub_broker.stream_buffer) == 0  # 100% stream buffer evacuation achieved!
    assert len(consumer.processed_winlogs) == 10
    
    # Verify winlog extensible forensic metadata preservation
    sample_winlog = consumer.processed_winlogs[5]
    assert sample_winlog.asset_id == test_asset_id
    assert sample_winlog.event_id == 4624
    assert sample_winlog.evtx_metadata["event_source"] == "DiskDeleter"
    assert sample_winlog.evtx_metadata["workstation_name"] == "PC-5"


@pytest.mark.asyncio
async def test_consumer_empty_queue_handling():
    """Verifies invoking process_batch on drained queue handles cleanly without raised exceptions."""
    stub_broker = StubTelemetryStreamBroker()
    consumer = TelemetryStreamConsumer(broker=stub_broker)
    res = await consumer.process_batch(batch_size=50)
    assert res == 0
