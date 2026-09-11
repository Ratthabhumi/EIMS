"""
==============================================================================
EIMS Query Layer - Telemetry Vitals & Anomaly Contextual Search Provider
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.search.provider import SearchProvider, SearchResult
from backend.domain.telemetry.models import TelemetryMetric

_TELEMETRY_TRIGGERS = (
    "telemetry", "metric", "metrics", "cpu", "ram", "gpu", "utilization",
    "spike", "vitals", "anomaly", "high cpu", "iops", "bandwidth"
)


class TelemetrySearchProvider(SearchProvider):
    """
    Contextual operational discovery provider for telemetry metrics.
    Guards against indexing time-series torrents: executes ONLY when the query
    invokes telemetry vitals or specific hardware diagnostics (e.g. 'cpu', 'gpu', 'anomaly').
    Aggregates to the host asset context rather than dumping individual ticks.
    """
    name = "telemetry"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        lowered = cleaned.lower()

        is_telemetry_query = any(trigger in lowered for trigger in _TELEMETRY_TRIGGERS)
        if not is_telemetry_query:
            return []

        # Target diagnostic payload keywords and/or CPU spikes when relevant
        pattern = f"%{cleaned}%"
        conditions = [
            cast(TelemetryMetric.diagnostic_payload, String).ilike(pattern),
            InfrastructureAsset.hostname.ilike(pattern),
        ]
        if any(term in lowered for term in ("cpu", "spike", "high", "utilization", "overload", "anomaly")):
            conditions.append(TelemetryMetric.cpu_utilization >= 75.0)

        stmt = (
            select(TelemetryMetric, InfrastructureAsset.hostname, InfrastructureAsset.lifecycle_state)
            .join(InfrastructureAsset, TelemetryMetric.asset_id == InfrastructureAsset.asset_id)
            .where(or_(*conditions))
            .order_by(TelemetryMetric.event_time.desc())
            .limit(min(limit, 5))  # Strict throttle preventing telemetry flood
        )

        rows = (await db.execute(stmt)).all()
        return [self._to_result(metric, hostname, state, cleaned) for metric, hostname, state in rows]

    @staticmethod
    def _to_result(metric: TelemetryMetric, hostname: str, state: str, query: str) -> SearchResult:
        is_spike = metric.cpu_utilization >= 85.0
        label = "High CPU Utilization" if is_spike else "Host Telemetry Stream"

        title = f"{label}: {hostname} ({metric.cpu_utilization:.1f}%)"
        time_str = metric.event_time.strftime("%Y-%m-%d %H:%M:%S") if metric.event_time else "n/a"
        subtitle = f"{time_str} • State: {state} • View Realtime Vitals"

        return SearchResult(
            type="telemetry",
            id=str(metric.metric_id),
            title=title,
            subtitle=subtitle,
            url=f"/observability?asset_id={metric.asset_id}",
            timestamp=metric.event_time,
            relevance=0.88 if is_spike else 0.80,
            result_kind="entity",
            metadata={
                "asset_id": str(metric.asset_id),
                "hostname": hostname,
                "cpu_utilization": metric.cpu_utilization,
                "diagnostic_payload": metric.diagnostic_payload,
            },
        )
