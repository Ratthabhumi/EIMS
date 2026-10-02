from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


class EventMetadata(BaseModel):
    eventId: str = "Unknown"
    provider: str = "Unknown"
    level: str = ""
    logName: str = ""
    timestamp: str = ""
    computer: str = ""
    isCritical: bool = False
    faultingApp: str = ""
    # Source-aware classification (optional: historical rows without these
    # fields continue to deserialize unchanged).
    sourceFamily: str = ""
    product: str = ""
    diagnosticCode: str = ""
    parserConfidence: float = 0.0
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str = ""
    sourceType: Literal["official", "community"] = "community"


class SolutionSummary(BaseModel):
    overview: str = ""
    causes: List[str] = []
    steps: List[str] = []
    # Evidence-first RCA (optional: older clients ignore unknown fields).
    evidence: List[str] = Field(default_factory=list)
    confidence: str = ""
    limitations: List[str] = Field(default_factory=list)
    nextEvidence: List[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    eventId: str
    provider: str
    description: str
    eventMetadata: EventMetadata = EventMetadata()
    aiSummary: str = ""
    solutionSummary: SolutionSummary = SolutionSummary()
    searchResults: List[SearchResult] = []
    historyId: Optional[int] = None


class FollowUpRequest(BaseModel):
    question: str
    eventId: str
    provider: str = "Unknown"
    language: str = "th"


class FollowUpResponse(BaseModel):
    answer: str


class TopError(BaseModel):
    eventId: str
    provider: str
    count: int

class DailyTrend(BaseModel):
    date: str
    count: int

class TypeDistribution(BaseModel):
    name: str
    value: int

class StatsResponse(BaseModel):
    totalLogs: int = 0
    criticalErrors: int = 0
    avgSearchTimeSec: float = 0.0
    topWeeklyError: Optional[TopError] = None
    dailyTrends: List[DailyTrend] = []
    typeDistribution: List[TypeDistribution] = []
