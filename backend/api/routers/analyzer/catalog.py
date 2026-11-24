"""Read-only knowledge catalog summary API.

Exposes the effective, database-backed governance counts. The canonical content
stays in the JSON catalogs; only lifecycle/review state comes from PostgreSQL.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.auth import get_current_user
from backend.domain.knowledge.service import KnowledgeNotFound, current_record, summary
from backend.infrastructure.database import get_db_session

catalog_router = APIRouter(prefix="/api/v1/analyzer/catalog", tags=["Analyzer Catalog"])


@catalog_router.get("/summary")
async def catalog_summary(
    _user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Canonical classification merged with the persisted overlay state."""
    return await summary(db)


@catalog_router.get("/record")
async def catalog_record(
    catalog_id: str = Query(..., min_length=3, max_length=200),
    _user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Current canonical record and trust (read-only; query param because ids may contain '/')."""
    try:
        return await current_record(db, catalog_id)
    except KnowledgeNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
