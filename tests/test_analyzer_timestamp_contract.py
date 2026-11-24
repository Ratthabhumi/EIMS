from datetime import UTC, datetime

from backend.domain.analyzer.models.history import AnalysisHistory


def test_analysis_history_default_is_utc_naive_for_legacy_column():
    before = datetime.now(UTC).replace(tzinfo=None)
    created_at = AnalysisHistory.__table__.c.created_at.default.arg(None)
    after = datetime.now(UTC).replace(tzinfo=None)

    assert created_at.tzinfo is None
    assert before <= created_at <= after
