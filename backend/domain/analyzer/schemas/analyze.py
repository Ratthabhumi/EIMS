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


class EvidenceRef(BaseModel):
    """One piece of evidence text and where it occurs. Line numbers are positions inside the SUBMITTED text
    (``lineBasis`` says so); they are not offsets into an original file."""
    text: str
    sourceFile: str = ""
    timestamp: str = ""
    lineNumbers: List[int] = Field(default_factory=list)
    occurrences: int = 1
    lineBasis: str = ""


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
    # Exact repeats are grouped (never silently dropped): every line number and the occurrence count are kept.
    evidenceRefs: List[EvidenceRef] = Field(default_factory=list)


class EvidenceContextLine(BaseModel):
    lineNumber: int
    text: str
    truncated: bool = False


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
    sourceContext: List[EvidenceContextLine] = Field(default_factory=list)
    # A bounded snapshot of decoded/extracted source, never reconstructed History.
    sourceContextOrigin: str = "unavailable"


class KnowledgeMatch(BaseModel):
    """Deterministic trust classification of the matched knowledge record.

    Set only by the server after synthesis; never produced or altered by a model.
    """
    classification: Literal[
        "context_match", "diagnostic_candidate_match", "source_verified_match",
        "validated_diagnostic_match", "approved_diagnostic_match",
        "version_compatible_match", "no_verified_match",
    ] = "no_verified_match"
    catalogId: Optional[str] = None
    lifecycleStatus: Optional[str] = None
    stale: bool = False
    versionScope: Optional[str] = None
    versionCompatible: Optional[bool] = None
    overlayAvailable: bool = True
    # direct = identity (and provider for Windows) confirmed; contextual = Event ID matches but the provider is
    # unspecified/unverified; none = no applicable record (including a record for a different provider).
    matchKind: Literal["direct", "contextual", "none"] = "none"
    matchBasis: Optional[str] = None
    note: str = ""


class GuidanceField(BaseModel):
    """One operational answer. ``not_stated``: the catalog has no such information (never filled in); ``unverified``: a human-supplied
    or derived item with a stated basis that is NOT confirmed; ``stated``: backed by an official source."""
    status: str = "not_stated"
    items: List[str] = Field(default_factory=list)
    source: str = ""
    basis: str = ""
    origin: str = ""


class GuidanceSource(BaseModel):
    title: str = ""
    url: str = ""
    scope: str = ""


class GuidanceLimitations(BaseModel):
    maturity: str = ""
    limitations: List[str] = Field(default_factory=list)


class OperationalGuidance(BaseModel):
    """What happened / why / inspect / act / risk / rollback / prove recovery, straight from the catalog record (read-only)."""
    whatHappened: str = ""
    why: GuidanceField = Field(default_factory=GuidanceField)
    inspect: GuidanceField = Field(default_factory=GuidanceField)
    recommendedAction: GuidanceField = Field(default_factory=GuidanceField)
    risk: GuidanceField = Field(default_factory=GuidanceField)
    rollback: GuidanceField = Field(default_factory=GuidanceField)
    recoveryVerification: GuidanceField = Field(default_factory=GuidanceField)
    requiredPermission: GuidanceField = Field(default_factory=GuidanceField)
    humanApproval: GuidanceField = Field(default_factory=GuidanceField)
    recoveryEvidence: GuidanceField = Field(default_factory=GuidanceField)
    recoverySuccessCriteria: GuidanceField = Field(default_factory=GuidanceField)
    operationalImpact: GuidanceField = Field(default_factory=GuidanceField)
    destructiveRisk: GuidanceField = Field(default_factory=GuidanceField)
    evidenceAndSource: List[GuidanceSource] = Field(default_factory=list)
    versionScope: str = ""
    confidenceLimitations: GuidanceLimitations = Field(default_factory=GuidanceLimitations)
    destructiveActions: List[str] = Field(default_factory=list)
    reviewState: str = ""
    catalogId: str = ""
    contentHash: str = ""
    missing: List[str] = Field(default_factory=list)


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
    # Server-assigned knowledge trust level (see KnowledgeMatch).
    knowledgeMatch: Optional[KnowledgeMatch] = None
    # Catalog-derived operational guidance (optional: absent for records without a linked catalog entry).
    operationalGuidance: Optional[OperationalGuidance] = None


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
    # Identity aliases so result views resolve history + follow-up uniformly.
    historyId: Optional[int] = None
    eventId: str = "Unknown"
    provider: str = "Unknown"
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
