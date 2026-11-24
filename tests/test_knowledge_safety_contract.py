import pytest
from pydantic import ValidationError

from backend.api.routers.analyzer.knowledge import KnowledgeProposalRequest


def _payload(**overrides):
    value = {
        "history_id": 1,
        "title": "Synthetic remediation knowledge",
        "resolution_status": "resolved",
        "root_cause": "A synthetic service account lacked the required permission.",
        "solution_steps": ["Grant the minimum permission and retest the affected API."],
        "evidence_notes": ["Synthetic permission-denied response was captured."],
        "risk_level": "high",
        "validation_steps": ["Verify the API returns the expected policy set."],
        "rollback_steps": ["Revert the permission change and restore the prior role."],
    }
    value.update(overrides)
    return value


def test_high_risk_knowledge_requires_validation_and_rollback():
    with pytest.raises(ValidationError, match="requires validation and rollback"):
        KnowledgeProposalRequest.model_validate(
            _payload(validation_steps=["Verify the API"], rollback_steps=[])
        )


def test_high_risk_knowledge_accepts_explicit_validation_and_rollback():
    request = KnowledgeProposalRequest.model_validate(_payload())
    assert request.risk_level == "high"
    assert request.validation_steps
    assert request.rollback_steps
