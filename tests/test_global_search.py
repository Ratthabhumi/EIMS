"""
==============================================================================
EIMS Automated Test Suite — Sprint 10 Global Search API
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
==============================================================================
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.domain.search.controller import get_search_service
from backend.domain.search.provider import SearchResult
from backend.main import app


def _make_result(res_type: str = "asset", title: str = "SRV-FIN-001") -> SearchResult:
    return SearchResult(
        type=res_type,
        id=str(uuid.uuid4()),
        title=title,
        subtitle="Active • 192.168.1.100",
        url="/endpoints?id=00000000-0000-0000-0000-000000000000",
        timestamp=datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc),
        relevance=0.95,
        metadata={"state": "Active", "score": 85},
    )


class StubGlobalSearchService:
    """Hermetic Global Search orchestrator stub honoring the controller call contract."""

    def __init__(self, results):
        self.results = results

    async def global_search(self, db, query, search_type=None, page=1, limit=20):
        data = self.results if search_type is None else [r for r in self.results if r.type == search_type]
        data = [r for r in data if query.lower() in (r.title + r.subtitle).lower()]
        total = len(data)
        start = (page - 1) * limit
        return data[start:start + limit], total


@pytest.fixture
def search_overrides(client: TestClient):
    """Injects the hermetic Global Search service stub scoped for the request lifetime."""
    service = StubGlobalSearchService([
        _make_result("asset", "SRV-FIN-001"),
        _make_result("audit", "TRANSITION_STATE"),
        _make_result("analysis", "LOGON FAILURE DETECTED"),
    ])
    app.dependency_overrides[get_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_search_service, None)


def test_search_returns_normalized_results(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search", params={"q": "SRV"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["type"] == "asset"
    assert item["title"] == "SRV-FIN-001"
    assert item["subtitle"]
    assert item["url"]
    assert item["timestamp"]
    assert 0.0 <= item["relevance"] <= 1.0
    assert body["pagination"]["total_records"] == 1
    assert body["pagination"]["current_page"] == 1


def test_search_type_filter(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search", params={"q": "STATE", "type": "audit"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert all(item["type"] == "audit" for item in body["data"])
    assert body["data"][0]["title"] == "TRANSITION_STATE"


def test_search_works_for_guest_without_token(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search", params={"q": "SRV"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_search_rejects_short_query(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search", params={"q": "a"})
    assert resp.status_code == 422


def test_search_requires_query_param(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search")
    assert resp.status_code == 422


def test_search_rejects_unknown_type(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search", params={"q": "SRV", "type": "hardware"})
    assert resp.status_code == 422


def test_search_pagination_slices_results(client: TestClient):
    from backend.domain.search.controller import get_search_service

    service = StubGlobalSearchService([
        _make_result("asset", "TRACK-A"),
        _make_result("audit", "TRACK-B"),
        _make_result("analysis", "TRACK-C"),
    ])
    app.dependency_overrides[get_search_service] = lambda: service
    try:
        resp = client.get("/api/v1/search", params={"q": "TRACK", "limit": 2, "page": 2})
    finally:
        app.dependency_overrides.pop(get_search_service, None)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["pagination"]["current_page"] == 2
    assert body["pagination"]["total_records"] == 3


def test_search_empty_result_set(search_overrides, client: TestClient):
    resp = client.get("/api/v1/search", params={"q": "zzzz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["pagination"]["total_records"] == 0


def test_search_provider_registry_contains_domains():
    from backend.domain.search.controller import search_service
    from backend.domain.search.registry import SearchProviderRegistry

    assert isinstance(search_service._registry, SearchProviderRegistry)
    names = {provider.name for provider in search_service._registry}
    assert names == {"asset", "audit", "analysis"}