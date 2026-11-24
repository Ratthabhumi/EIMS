"""Open-access Unified Knowledge Catalog listing (read-only projection)."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from backend.domain.knowledge.unified_catalog import identity_evidence, list_catalog

router = APIRouter(tags=["Unified Knowledge Catalog"])

SortField = Literal[
    "catalog_id", "-catalog_id", "title", "-title", "product", "-product",
    "cert_class", "-cert_class", "parser_linkage", "-parser_linkage",
]


@router.get("/catalog")
async def get_unified_catalog(
    response: Response,
    q: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    parser_linkage: Annotated[
        Literal[
            "analyzer_matchable",
            "cert_parser_linked_only",
            "parser_mapped_reference",
            "not_linked",
        ]
        | None,
        Query(),
    ] = None,
    analyzer_availability: Annotated[Literal["matchable", "not_matchable"] | None, Query()] = None,
    eligibility: Annotated[Literal["ELIGIBLE", "BLOCKED", "INELIGIBLE"] | None, Query()] = None,
    cert_class: Annotated[Literal["A", "B", "C", "D", "E", "F"] | None, Query()] = None,
    product: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort: Annotated[SortField, Query()] = "catalog_id",
):
    """Governed inventory projection with explicit Analyzer vs certification fields."""
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    return list_catalog(
        q=q,
        parser_linkage=parser_linkage,
        analyzer_availability=analyzer_availability,
        eligibility=eligibility,
        cert_class=cert_class,
        product=product,
        offset=offset,
        limit=limit,
        sort=sort,
    )


@router.get("/catalog/identity-evidence")
async def get_catalog_identity_evidence():
    """Phase-1 machine-verifiable identity claims (read-only)."""
    return identity_evidence()
