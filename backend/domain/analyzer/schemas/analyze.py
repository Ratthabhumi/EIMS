from pydantic import BaseModel
from typing import List, Literal, Optional


class EventMetadata(BaseModel):
    eventId: str = "Unknown"
    provider: str = "Unknown"
    level: str = ""
    logName: str = ""
    timestamp: str = ""
    computer: str = ""
    isCritical: bool = False
    faultingApp: str = ""


class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str = ""
    sourceType: Literal["official", "community"] = "community"


class SolutionSummary(BaseModel):
    overview: str = ""
    causes: List[str] = []
    steps: List[str] = []


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
