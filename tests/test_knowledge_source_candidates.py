import json
from pathlib import Path

CANDIDATE_FILE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "knowledge-source-candidates"
    / "official-vendor-candidates.v1.json"
)


def test_official_vendor_candidate_corpus_is_structured_and_not_approved():
    data = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))
    candidates = data["candidates"]

    assert data["corpus_type"] == "official_vendor_source_candidates"
    assert data["approval_state"] == "candidate_only_not_approved_knowledge"
    assert data["policy"]["exact_identity_retrieval_enabled"] is False
    assert data["policy"]["production_knowledge_import_enabled"] is False
    assert len(candidates) == 20
    from collections import Counter
    assert Counter(item["vendor"] for item in candidates) == {
        "Microsoft": 5, "Broadcom VMware": 6, "Veeam": 4, "Fortinet": 5
    }
    assert len({item["id"] for item in candidates}) == len(candidates)

    for item in candidates:
        assert item["review_state"] == "pending_domain_review"
        assert item["evidence_status"] == "official_source_verified"
        assert item["url"].startswith("https://")
        assert item["version_scope"].strip()
        assert item["applicability"].strip()
        assert item["prerequisites"]
        assert item["evidence"]
        assert item["limitations"]
        assert item["next_checks"]
        assert item["validation"]
        assert item["rollback"]
        assert item["risk"] in {"low", "medium", "high", "critical"}


def test_high_risk_candidates_have_explicit_validation_and_rollback():
    data = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))
    high_risk = [
        item for item in data["candidates"]
        if item["risk"] in {"high", "critical"}
    ]
    assert high_risk
    for item in high_risk:
        assert item["validation"]
        assert item["rollback"]


def test_database_importer_is_dry_run_by_default_and_hashes_catalogue():
    from tools.import_knowledge_source_candidates import canonical_hash, load_catalogue

    data, candidates = load_catalogue()
    assert len(candidates) == 20
    assert all(canonical_hash(item) == canonical_hash(dict(item)) for item in candidates)
    assert all(item["review_state"] == "pending_domain_review" for item in candidates)
    assert data["policy"]["production_knowledge_import_enabled"] is False


def test_candidate_source_hash_changes_when_vendor_evidence_changes():
    from tools.import_knowledge_source_candidates import canonical_hash, load_catalogue

    _, candidates = load_catalogue()
    original = dict(candidates[0])
    changed = {**original, "limitations": [*original["limitations"], "Synthetic changed-source marker"]}
    assert canonical_hash(original) != canonical_hash(changed)
