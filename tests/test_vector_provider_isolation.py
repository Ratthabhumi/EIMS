"""The legacy vector knowledge path must not bypass provider isolation (reachable from summary.build_summary)."""
import pytest

from backend.domain.analyzer.services import vector_db

f = vector_db._is_usable_knowledge_row


def _row(provider=None, scope="provider_specific", event="1000", family="windows_event", status="approved"):
    knowledge = {"sourceFamily": family, "diagnosticIdentity": event, "reviewStatus": status,
                 "reviewedBy": "reviewer", "reviewedAt": "2026-11-20T00:00:00Z"}
    if provider is not None or scope:
        knowledge.update(provider=provider, providerScope=scope)
    return {"overview": "x", "_knowledge": knowledge}


def test_same_provider_is_usable_and_case_insensitive():
    assert f("1000", 0, "1000", "windows_event", 0.01, row_solution_json=_row("Application Error"),
             request_provider="application  error")


@pytest.mark.parametrize("request_provider", [".NET Runtime", "", None, "unknown"])
def test_other_or_missing_provider_never_matches_even_when_semantically_identical(request_provider):
    assert not f("1000", 9, "1000", "windows_event", 0.0, row_solution_json=_row("Application Error"),
                 request_provider=request_provider)


def test_cross_identity_semantic_neighbour_cannot_bridge_providers():
    # Different Event ID + tiny distance is allowed only inside one provider.
    assert f("1001", 0, "1000", "windows_event", 0.05, row_solution_json=_row("P", event="1001"), request_provider="P")
    assert not f("1001", 0, "1000", "windows_event", 0.05, row_solution_json=_row("P", event="1001"), request_provider="Q")


def test_legacy_unqualified_and_generic_rows_never_match_windows():
    legacy = {"overview": "x", "_knowledge": {"sourceFamily": "windows_event", "diagnosticIdentity": "1000",
              "reviewStatus": "approved", "reviewedBy": "r", "reviewedAt": "t"}}
    assert not f("1000", 0, "1000", "windows_event", 0.0, row_solution_json=legacy, request_provider="Application Error")
    assert not f("1000", 0, "1000", "windows_event", 0.0, row_solution_json=_row(None, scope="generic"),
                 request_provider="Application Error")
    assert not f("1000", 0, "1000", "windows_event", 0.0, row_solution_json=_row(None, scope="unknown"),
                 request_provider="Application Error")


def test_pending_row_is_never_usable_and_vendor_families_are_unaffected():
    assert not f("1000", 9, "1000", "windows_event", 0.0, row_solution_json=_row("P", status="pending"), request_provider="P")
    vendor = {"overview": "v", "_knowledge": {"sourceFamily": "cisco_asa", "diagnosticIdentity": "ASA-1",
              "reviewStatus": "approved", "reviewedBy": "r", "reviewedAt": "t"}}
    assert f("ASA-1", 0, "ASA-1", "cisco_asa", 0.0, row_solution_json=vendor)


def test_add_solution_records_provider_scope_on_pending_candidates(monkeypatch):
    import asyncio
    saved = {}

    class DB:
        async def execute(self, *_a, **_k):
            class R:
                def scalars(self_inner):
                    class S:
                        def first(self_i2):
                            return None
                    return S()
            return R()
        def add(self, obj): saved["obj"] = obj
        async def commit(self): pass
        async def rollback(self): pass

    async def fake_rollback(db): return True
    monkeypatch.setattr(vector_db, "rollback_read_only_transaction", fake_rollback)
    monkeypatch.setattr(vector_db, "_get_embedding", lambda *a, **k: [0.1] * 384)
    asyncio.run(vector_db.add_solution(DB(), "1000", "d", {"overview": "o"}, feedback_score=1,
                                       source_family="windows_event", diagnostic_identity="1000", provider="Application Error"))
    knowledge = saved["obj"].solution_json["_knowledge"]
    assert (knowledge["reviewStatus"], knowledge["provider"], knowledge["providerScope"]) == ("pending", "Application Error", "provider_specific")


def test_add_solution_never_overwrites_another_providers_row(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    existing = SimpleNamespace(event_id="1000", description="d", feedback_score=3,
                               solution_json={"overview": "A", "_knowledge": {"provider": "Provider A", "providerScope": "provider_specific",
                                                                              "reviewStatus": "approved", "reviewedBy": "r", "reviewedAt": "t"}})
    added = []

    class DB:
        async def execute(self, *_a, **_k):
            class R:
                def scalars(self_inner):
                    class S:
                        def first(self_i2):
                            return existing
                    return S()
            return R()
        def add(self, obj): added.append(obj)
        async def commit(self): pass
        async def rollback(self): pass

    async def ok(db): return True
    monkeypatch.setattr(vector_db, "rollback_read_only_transaction", ok)
    monkeypatch.setattr(vector_db, "_get_embedding", lambda *a, **k: [0.1] * 384)
    asyncio.run(vector_db.add_solution(DB(), "1000", "d", {"overview": "B"}, feedback_score=-1,
                                       source_family="windows_event", provider="Provider B"))
    assert existing.feedback_score == 3 and existing.solution_json["_knowledge"]["reviewStatus"] == "approved"
