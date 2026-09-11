from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from backend.domain.analyzer.schemas.analyze import SearchResult, SolutionSummary, EventMetadata


class HistoryBase(BaseModel):
    eventId: str
    provider: str
    parseMethod: Optional[str] = ""
    description: Optional[str] = ""
    aiSummary: Optional[str] = ""
    solutionSummary: Optional[SolutionSummary] = None
    eventMetadata: Optional[EventMetadata] = None
    searchResults: List[SearchResult] = []
    searchTimeMs: Optional[float] = 0.0


class HistoryCreate(HistoryBase):
    pass


class HistoryResponse(HistoryBase):
    id: int
    created_at: datetime
    username: Optional[str] = None
    feedback_by: Optional[str] = None
    feedback_score: Optional[int] = None

    model_config = {"from_attributes": True}
