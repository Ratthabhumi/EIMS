"""
==============================================================================
EIMS Query Layer - USB Auditor & Endpoint Evidence Search Provider
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from sqlalchemy import String, and_, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.search.provider import SearchProvider, SearchResult


class UsbAuditorSearchProvider(SearchProvider):
    """
    Endpoint evidence provider indexing assets enrolled or updated via the
    offline USB Auditor agent (`InfrastructureAsset.offline_report_data`).
    Matches USB device reports, computer name, username, Windows build, MAC address,
    and security evaluation findings.
    """
    name = "usb"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        lowered = cleaned.lower()
        pattern = f"%{cleaned}%"

        is_usb_generic_query = lowered in ("usb", "usb auditor", "auditor", "removable media", "offline report")

        # Base predicate: Asset must possess persisted offline USB Auditor report data
        has_report = InfrastructureAsset.offline_report_data.isnot(None)

        if is_usb_generic_query:
            stmt = (
                select(InfrastructureAsset)
                .where(has_report)
                .order_by(InfrastructureAsset.updated_at.desc())
                .limit(limit)
            )
        else:
            stmt = (
                select(InfrastructureAsset)
                .where(
                    and_(
                        has_report,
                        or_(
                            InfrastructureAsset.hostname.ilike(pattern),
                            InfrastructureAsset.canonical_ip.ilike(pattern),
                            InfrastructureAsset.cryptographic_fingerprint.ilike(pattern),
                            cast(InfrastructureAsset.offline_report_data, String).ilike(pattern),
                        ),
                    )
                )
                .order_by(InfrastructureAsset.updated_at.desc())
                .limit(limit)
            )

        assets = (await db.execute(stmt)).scalars().all()
        return [self._to_result(asset, cleaned, is_usb_generic_query) for asset in assets]

    @staticmethod
    def _to_result(asset: InfrastructureAsset, query: str, is_generic: bool) -> SearchResult:
        report = asset.offline_report_data or {}
        system_info = report.get("system", {})
        metadata_info = report.get("metadata", {})

        comp_name = system_info.get("computer_name") or asset.hostname
        edition = system_info.get("windows_edition", "Windows")
        scan_time = system_info.get("scan_timestamp") or (metadata_info.get("generated_at") or "")
        score = asset.current_compliance_score

        subtitle_parts = [f"Score: {score}%", edition]
        if scan_time:
            subtitle_parts.append(f"Scanned: {scan_time}")

        relevance = UsbAuditorSearchProvider._compute_relevance(asset, query, is_generic)

        return SearchResult(
            type="usb",
            id=str(asset.asset_id),
            title=f"USB Audit: {comp_name}",
            subtitle=" • ".join(subtitle_parts),
            url=f"/endpoints?id={asset.asset_id}",
            timestamp=asset.updated_at or asset.created_at,
            relevance=relevance,
            result_kind="entity",
            metadata={
                "asset_id": str(asset.asset_id),
                "compliance_score": score,
                "computer_name": comp_name,
                "windows_edition": edition,
                "ip_address": asset.canonical_ip,
                "mac_address": asset.cryptographic_fingerprint,
                "auditor_version": metadata_info.get("auditor_version"),
            },
        )

    @staticmethod
    def _compute_relevance(asset: InfrastructureAsset, query: str, is_generic: bool) -> float:
        if is_generic:
            return 0.95
        lowered = query.lower()
        if asset.hostname.lower() == lowered:
            return 1.00
        if asset.cryptographic_fingerprint.lower() == lowered:
            return 0.98
        if asset.hostname.lower().startswith(lowered):
            return 0.90
        return 0.82
