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


class IncidentAssessment(BaseModel):
    """Structural incident sketch persisted with the analysis.

    Reports the OBSERVED failure sequence (first -> terminal) and what is
    still missing.  It never asserts one failure caused another unless the
    evidence proves it.
    """

    firstMeaningfulFailure: str = ""
    terminalFailure: str = ""
    timeline: List[str] = Field(default_factory=list)
    operationStage: str = ""
    diagnosticSignatures: List[str] = Field(default_factory=list)
    observedPaths: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    nextEvidence: List[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """One observed evidence line with file provenance.

    Every field is populated ONLY from observed evidence — filename, line
    number, path, and timestamp are never invented.  Missing fields stay "".
    """

    sourceFile: str = ""
    lineNumber: int = 0
    timestamp: str = ""
    message: str = ""
    signature: str = ""
    observedPath: str = ""


class SolutionSummary(BaseModel):
    overview: str = ""
    causes: List[str] = []
    steps: List[str] = []
    # Evidence-first RCA (optional: older clients ignore unknown fields).
    evidence: List[str] = Field(default_factory=list)
    confidence: str = ""
    limitations: List[str] = Field(default_factory=list)
    nextEvidence: List[str] = Field(default_factory=list)
    # Structured incident sketch (optional: older records/rows ignore it).
    incident: Optional[IncidentAssessment] = None
    # Structured evidence with file provenance (bundle path; single-file
    # analyses keep using `evidence` for backward compatibility).
    evidenceItems: List[EvidenceItem] = Field(default_factory=list)


class BundleFileResult(BaseModel):
    filename: str = ""
    sizeBytes: int = 0
    sha256: str = ""
    sourceFamily: str = ""
    product: str = ""
    diagnosticCode: str = ""
    parserConfidence: float = 0.0


class BundleResponse(BaseModel):
    bundleId: Optional[int] = None
    files: List[BundleFileResult] = Field(default_factory=list)
    correlationConfidence: str = "none"
    correlationReasons: List[str] = Field(default_factory=list)
    correlatedSources: List[str] = Field(default_factory=list)
    eventMetadata: EventMetadata = EventMetadata()
    aiSummary: str = ""
    solutionSummary: SolutionSummary = SolutionSummary()
    searchResults: List[SearchResult] = Field(default_factory=list)


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
    eventId: str = "Unknown"
    provider: str = "Unknown"
    language: str = "th"
    # When present, the analysis service reloads the stored context (source
    # family, diagnostic code, product, evidence) from the history row.
    historyId: Optional[int] = None


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
