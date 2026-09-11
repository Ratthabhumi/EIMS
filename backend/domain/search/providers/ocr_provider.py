"""
==============================================================================
EIMS Query Layer - Sticker OCR & Physical Device Evidence Search Provider
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from typing import Any
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.asset_registry.models import OCRRegistrationRecord
from backend.domain.search.provider import SearchProvider, SearchResult


class OcrSearchProvider(SearchProvider):
    """
    Physical hardware device evidence provider searching through asynchronous
    OCR Sticker Registration workflow records (`OCRRegistrationRecord`).
    Matches extracted serial numbers, models, brand labels, and extraction statuses.
    """
    name = "ocr"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        cleaned = query.strip()
        lowered = cleaned.lower()
        pattern = f"%{cleaned}%"

        is_ocr_generic = lowered in ("ocr", "sticker", "sticker ocr", "barcode", "label", "tesseract")

        if is_ocr_generic:
            stmt = select(OCRRegistrationRecord).limit(limit)
        else:
            stmt = (
                select(OCRRegistrationRecord)
                .where(
                    or_(
                        OCRRegistrationRecord.extraction_status.ilike(pattern),
                        cast(OCRRegistrationRecord.parsed_raw_text, String).ilike(pattern),
                        OCRRegistrationRecord.minio_object_uri.ilike(pattern),
                    )
                )
                .limit(limit)
            )

        records = (await db.execute(stmt)).scalars().all()
        return [self._to_result(rec, cleaned, is_ocr_generic) for rec in records]

    @staticmethod
    def _to_result(record: OCRRegistrationRecord, query: str, is_generic: bool) -> SearchResult:
        parsed = record.parsed_raw_text or {}
        serial = (
            parsed.get("serial_number")
            or parsed.get("serial")
            or parsed.get("serial_no")
            or parsed.get("mac_address")
            or parsed.get("asset_tag")
        )
        model = parsed.get("model") or parsed.get("device_model") or parsed.get("brand") or "Hardware Label"

        display_name = serial if serial else f"Record {str(record.record_id)[:8]}"
        title = f"Sticker OCR: {display_name}"

        subtitle_parts = [f"Status: {record.extraction_status}", str(model)]
        if record.asset_id:
            subtitle_parts.append(f"Linked Asset: {str(record.asset_id)[:8]}")

        dest_url = f"/endpoints?id={record.asset_id}" if record.asset_id else "/ocr-history"
        relevance = OcrSearchProvider._compute_relevance(record, query, serial, is_generic)

        return SearchResult(
            type="ocr",
            id=str(record.record_id),
            title=title,
            subtitle=" • ".join(subtitle_parts),
            url=dest_url,
            timestamp=None,  # Real model has no created_at/updated_at timestamp
            relevance=relevance,
            result_kind="entity",
            metadata={
                "record_id": str(record.record_id),
                "asset_id": str(record.asset_id) if record.asset_id else None,
                "status": record.extraction_status,
                "serial_number": serial,
                "model": model,
                "minio_uri": record.minio_object_uri,
            },
        )

    @staticmethod
    def _compute_relevance(record: OCRRegistrationRecord, query: str, serial: Any, is_generic: bool) -> float:
        if is_generic:
            return 0.95
        lowered = query.lower()
        if serial and str(serial).lower() == lowered:
            return 1.00
        if serial and str(serial).lower().startswith(lowered):
            return 0.92
        if record.extraction_status.lower() == lowered:
            return 0.85
        return 0.75
