"""
==============================================================================
EIMS Query Layer - Asset Search Provider (Sprint 10)
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.search.provider import SearchProvider, SearchResult


class AssetSearchProvider(SearchProvider):
    """
    Primary Global Search domain. Applies partial substring matching on
    `hostname`, `canonical_ip`, `cryptographic_fingerprint`, and
    `offline_report_data`, alongside lifecycle state matching.
    """
    name = "asset"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        pattern = f"%{cleaned}%"
        stmt = (
            select(InfrastructureAsset)
            .where(
                or_(
                    InfrastructureAsset.hostname.ilike(pattern),
                    InfrastructureAsset.canonical_ip.ilike(pattern),
                    InfrastructureAsset.cryptographic_fingerprint.ilike(pattern),
                    InfrastructureAsset.lifecycle_state.ilike(cleaned),
                    cast(InfrastructureAsset.offline_report_data, String).ilike(pattern),
                )
            )
            .order_by(InfrastructureAsset.hostname.asc())
            .limit(limit)
        )
        assets = (await db.execute(stmt)).scalars().all()
        return [self._to_result(asset, cleaned) for asset in assets]

    @staticmethod
    def _to_result(asset: InfrastructureAsset, query: str) -> SearchResult:
        return SearchResult(
            type="asset",
            id=str(asset.asset_id),
            title=asset.hostname,
            subtitle=f"{asset.lifecycle_state} • {asset.canonical_ip}",
            url=f"/endpoints?id={asset.asset_id}",
            timestamp=asset.updated_at or asset.created_at,
            relevance=AssetSearchProvider._compute_relevance(asset, query),
            result_kind="entity",
            metadata={
                "state": asset.lifecycle_state,
                "compliance_score": asset.current_compliance_score,
            },
        )

    @staticmethod
    def _compute_relevance(asset: InfrastructureAsset, query: str) -> float:
        lowered = query.lower()
        hostname_lower = asset.hostname.lower()
        ip_lower = asset.canonical_ip.lower()

        if hostname_lower == lowered:
            return 1.00
        if asset.cryptographic_fingerprint == query:
            return 0.95
        if hostname_lower.startswith(lowered) or asset.canonical_ip == query:
            return 0.90
        if ip_lower.startswith(lowered):
            return 0.85
        if asset.lifecycle_state.lower() == lowered:
            return 0.80
        if lowered in hostname_lower or lowered in ip_lower:
            return 0.75
        return 0.70