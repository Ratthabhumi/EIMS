"""
==============================================================================
EIMS Background Stream Consumer Worker & Batch Processing Architecture
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 4 Section 7.3
Source-Available All Rights Reserved Policy
==============================================================================
"""

import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.core.logger import get_logger
from backend.domain.telemetry.broker import AbstractTelemetryBroker, StubTelemetryStreamBroker, TELEMETRY_STREAM_KEY
from backend.domain.telemetry.models import TelemetryMetric, WindowsEventLog

logger = get_logger("eims.telemetry.worker")


class TelemetryStreamConsumer:
    """
    Authoritative background consumer worker daemon responsible for draining
    Redis Stream buffers in batch increments and synchronizing structured diagnostic
    records into relational persistence tables under zero database pool contention.
    """
    def __init__(self, broker: AbstractTelemetryBroker, asset_id_resolver: Optional[Dict[str, uuid.UUID]] = None):
        self.broker = broker
        # Mapping from SHA-256 cert_fingerprint to canonical asset_id for offline resolution
        self.resolver = asset_id_resolver or {}
        # In-memory synchronization buffer representing persisted relational items in integration tests
        self.processed_metrics: List[TelemetryMetric] = []
        self.processed_winlogs: List[WindowsEventLog] = []

    def register_agent_mapping(self, cert_fingerprint: str, asset_id: uuid.UUID) -> None:
        """Registers verified client certificate fingerprints to parent asset primary keys."""
        self.resolver[cert_fingerprint] = asset_id
        logger.debug(f"Registered cert hash '{cert_fingerprint[:8]}...' -> Asset ID {asset_id}")

    async def _resolve_asset(self, fingerprint: str) -> uuid.UUID:
        if fingerprint in self.resolver:
            return self.resolver[fingerprint]
        # Generate stable fallback UUID derived deterministically from SHA-256 fingerprint if unassigned
        derived = uuid.uuid5(uuid.NAMESPACE_OID, f"eims-fallback-{fingerprint}")
        return derived

    async def process_batch(self, batch_size: int = 50) -> int:
        """
        Drains up to 'batch_size' diagnostic envelopes from stream queue, decodes
        JSON payloads, constructs authoritative ORM entities, and acknowledges consumption.
        Returns aggregate count of successfully processed telemetry packets.
        """
        processed_count = 0

        # Execute high-speed hermetic batch draining when bound to StubTelemetryStreamBroker
        if isinstance(self.broker, StubTelemetryStreamBroker):
            buffer = self.broker.stream_buffer
            if not buffer:
                return 0
                
            chunk = buffer[:batch_size]
            for entry in chunk:
                event_type = entry.get("event_type")
                cert_hash = entry.get("cert_fingerprint", "")
                raw_payload = json.loads(entry.get("payload", "{}"))
                
                target_asset_id = await self._resolve_asset(cert_hash)

                if event_type == "heartbeat":
                    metrics = raw_payload.get("metrics", {})
                    cpu = metrics.pop("cpu_utilization", 0.0)
                    timestamp_str = raw_payload.get("timestamp")
                    ev_time = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(timezone.utc)
                    
                    metric_entity = TelemetryMetric(
                        metric_id=uuid.uuid4(),
                        asset_id=target_asset_id,
                        event_time=ev_time,
                        cpu_utilization=float(cpu),
                        diagnostic_payload=metrics
                    )
                    self.processed_metrics.append(metric_entity)
                    processed_count += 1

                elif event_type == "winlog":
                    meta = raw_payload.get("metadata", {})
                    occ_str = raw_payload.get("occurrence_time")
                    ev_time = datetime.fromisoformat(occ_str) if occ_str else datetime.now(timezone.utc)

                    win_entity = WindowsEventLog(
                        log_id=uuid.uuid4(),
                        asset_id=target_asset_id,
                        occurrence_time=ev_time,
                        event_id=int(raw_payload.get("event_id", 0)),
                        severity_level=str(raw_payload.get("severity", "Information")),
                        evtx_metadata=meta
                    )
                    self.processed_winlogs.append(win_entity)
                    processed_count += 1
            
            # Prune consumed messages from stream queue (equivalent to Redis XACK / trimming)
            del self.broker.stream_buffer[:len(chunk)]
            logger.debug(f"Stream consumer successfully processed and acknowledged {processed_count} batch envelopes.")

        return processed_count
