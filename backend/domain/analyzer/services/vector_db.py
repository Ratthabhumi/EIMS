import re

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.core.config import settings
from backend.domain.analyzer.models.vector import VectorKnowledge
from backend.domain.analyzer.services.verified_knowledge import PROVIDER_BEARING_FAMILIES, norm_provider
from backend.domain.analyzer.services.vendor_parsers import is_vendor_diagnostic_code
from backend.infrastructure.database import rollback_read_only_transaction

# Cross-identity distance gate: a candidate whose diagnostic identity
# differs from the request is only reusable when it is genuinely close.
CROSS_IDENTITY_MAX_DISTANCE = 0.45

_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]+\b")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_SID_RE = re.compile(r"\bS-1-\d+(?:-\d+)+\b")
_SECRET_RE = re.compile(
    r"(password|passwd|pwd|token|secret|api[_-]?key|authorization)"
    r"(\s*[:=]\s*)(\S+)",
    re.IGNORECASE,
)
_SESSION_ID_RE = re.compile(
    r"\b(sessions?[_-]?id|jobsessionid|instanceid|task[_-]?id)"
    r"(\s*[:=]\s*)(\S+)",
    re.IGNORECASE,
)
_LONG_HEX_RE = re.compile(r"\b[0-9a-fA-F]{24,}\b")


def _mask_ipv6(match: re.Match) -> str:
    token = match.group(0)
    # Require a hex letter so clock strings like 12:34:56 are never masked.
    if re.search(r"[a-fA-F]", token):
        return "<IP6>"
    return token


def redact_for_embedding(text_content: str) -> str:
    """Normalize volatile infrastructure identifiers before embedding.

    Masks IPs, UUIDs/GUIDs, Windows SIDs, secret assignments, session/job
    identifiers and long hex tokens.  Human-readable labels are preserved
    ("JobSessionID=<ID>") so semantics survive while values cannot leak
    into the vector space.  Raw AnalysisHistory evidence is NOT altered.
    """
    if not text_content:
        return ""
    out = _IPV4_RE.sub("<IP>", text_content)
    out = _IPV6_RE.sub(_mask_ipv6, out)
    out = _UUID_RE.sub("<ID>", out)
    out = _SID_RE.sub("<SID>", out)
    out = _SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<REDACTED>", out)
    out = _SESSION_ID_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}<ID>", out)
    out = _LONG_HEX_RE.sub("<TOKEN>", out)
    return out

_local_model = None

def _get_local_model():
    global _local_model
    if _local_model is None:
        try:
            from fastembed import TextEmbedding
            # BAAI/bge-small-en-v1.5 & all-MiniLM-L6-v2 are 384 dimensions, running on ONNX runtime (ultra fast)
            _local_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        except Exception as e:
            try:
                from sentence_transformers import SentenceTransformer
                _local_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as se:
                print(f"Failed to load local embedding model: {e} | {se}")
    return _local_model

def _get_embedding(text_content: str, api_key: str | None = None) -> list[float]:
    """Generates 384-dimensional dense semantic embedding locally (Free, Ultra-fast, 100% Offline)."""
    if not text_content or not text_content.strip():
        return []
    
    # 1. Primary: High-speed Local ONNX FastEmbed / SentenceTransformer
    model = _get_local_model()
    if model is not None:
        try:
            if hasattr(model, 'embed'):
                # FastEmbed returns a generator of numpy arrays
                embeddings = list(model.embed([text_content.strip()]))
                return embeddings[0].tolist()
            elif hasattr(model, 'encode'):
                embedding = model.encode(text_content.strip(), normalize_embeddings=True)
                return embedding.tolist()
        except Exception as e:
            print(f"Local Embedding generation error: {e}")

    # No cloud fallback: knowledge retrieval is local-only and fails closed when
    # the local embedding model is unavailable.
    return []

async def add_solution(
    db: AsyncSession, 
    event_id: str, 
    description: str, 
    solution_summary: dict, 
    feedback_score: int = 0, 
    api_key: str | None = None,
    source_family: str | None = None,
    diagnostic_identity: str | None = None,
    provider: str | None = None,
):
    """Store a feedback-tagged knowledge candidate; it remains pending review.

    A thumbs-up records usefulness, not root-cause verification. Shared retrieval
    requires an explicit reviewer approval marker. Negative feedback quarantines
    an exact existing row; it never creates a new candidate.
    """
    # Hardened (AUTH_MODE=secure) deployments never publish History into the shared, ownerless vector namespace.
    # This is a data-ownership boundary, independent of application login (which does not exist): shared rows carry
    # no owner, so exporting a possibly user-attributed History row there would leak it to every reader.
    # Default local/demo mode (single shared open-access identity) keeps the vector export available.
    if settings.AUTH_MODE.lower() == 'secure':
        return None
    if await rollback_read_only_transaction(db) is False:
        # Vector export is best-effort; do not hold a dirty caller transaction
        # while waiting for local embedding inference.
        return

    sol_dict = dict(solution_summary) if isinstance(solution_summary, dict) else {}
    if source_family or diagnostic_identity:
        sol_dict["_knowledge"] = {
            "sourceFamily": str(source_family or ""),
            "diagnosticIdentity": str(diagnostic_identity or event_id or ""),
            # Provider scope (Windows event IDs are reused by unrelated providers). Never inferred from the Event ID.
            "provider": str(provider or "").strip() or None,
            "providerScope": "provider_specific" if str(provider or "").strip() else "unknown",
            "reviewStatus": "pending",
            "reviewedBy": None,
            "reviewedAt": None,
        }

    # Embedding work can be CPU-heavy. Complete it before the first DB query so
    # an idle request session does not hold a pooled connection during inference.
    embedding = None
    if feedback_score >= 0:
        document_text = redact_for_embedding(f"Event ID: {event_id}. Description: {description}")
        try:
            import asyncio
            embedding = await asyncio.to_thread(_get_embedding, document_text, api_key)
        except Exception:
            embedding = _get_embedding(document_text, api_key)

    try:
        existing = (await db.execute(
            select(VectorKnowledge).filter(
                VectorKnowledge.event_id == str(event_id),
                VectorKnowledge.description == description,
            )
        )).scalars().first()
        if existing is not None and (source_family or "") in PROVIDER_BEARING_FAMILIES:
            prior = (getattr(existing, "solution_json", None) or {}).get("_knowledge") or {}
            if norm_provider(prior.get("provider")) != norm_provider(provider):
                existing = None  # another provider's (or an unqualified) row is never overwritten or re-scored
    except Exception as e:
        print(f"Failed to look up Vector DB row: {e}")
        if await rollback_read_only_transaction(db) is False:
            return
        if feedback_score < 0:
            return
        existing = None

    if existing is not None:
        # Quarantine path: a thumbs-down lands here and the row becomes
        # non-retrievable via the feedback_score guardrail below.
        existing.feedback_score = feedback_score
        if sol_dict:
            existing.solution_json = sol_dict
        if feedback_score >= 0 and embedding:
            existing.embedding = embedding
        try:
            await db.commit()
        except Exception as e:
            print(f"Failed to update Vector DB row: {e}")
            await db.rollback()
        return

    if feedback_score < 0:
        # Nothing to quarantine: release the read-only lookup before returning.
        await rollback_read_only_transaction(db)
        return

    if not embedding:
        await rollback_read_only_transaction(db)
        return

    try:
        new_knowledge = VectorKnowledge(
            event_id=str(event_id),
            description=description,
            embedding=embedding,
            solution_json=sol_dict,
            feedback_score=feedback_score,
        )
        db.add(new_knowledge)
        await db.commit()
    except Exception as e:
        print(f"Failed to save to Vector DB: {e}")
        await db.rollback()

def _is_usable_knowledge_row(
    row_event_id: object,
    row_score: object,
    request_identity: str,
    request_family: str,
    distance: float,
    max_distance: float = CROSS_IDENTITY_MAX_DISTANCE,
    row_solution_json: dict | None = None,
    request_provider: str | None = None,
) -> bool:
    """Pure, fail-closed retrieval policy (unit-testable, no database).

    A positive feedback score means "helpful", not "verified". Retrieval therefore
    requires an explicit human review marker, reviewer identity and review time.
    Only the same source family is eligible; vendor diagnostics require exact codes.
    """
    try:
        score = int(row_score) if row_score is not None else 0
    except (TypeError, ValueError):
        score = 0
    if score < 0:
        return False

    req_family = str(request_family or "").strip()
    req_id = str(request_identity or "").strip()
    if not req_family or req_family == "unknown_text" or not req_id or req_id == "Unknown":
        return False

    knowledge = (row_solution_json or {}).get("_knowledge") if isinstance(row_solution_json, dict) else None
    if not isinstance(knowledge, dict):
        return False
    if str(knowledge.get("reviewStatus") or "").strip().lower() != "approved":
        return False
    if not str(knowledge.get("reviewedBy") or "").strip() or not str(knowledge.get("reviewedAt") or "").strip():
        return False

    row_family = str(knowledge.get("sourceFamily") or "").strip()
    row_diag = str(knowledge.get("diagnosticIdentity") or row_event_id or "").strip()
    if not row_family or not row_diag or row_family != req_family:
        return False

    # Provider isolation: for provider-bearing families (Windows events) only an entry written for the SAME provider is
    # usable. Legacy/unqualified rows, other providers and a missing request provider never match, and semantic
    # similarity can never bridge providers.
    if req_family in PROVIDER_BEARING_FAMILIES:
        wanted = norm_provider(request_provider)
        if not wanted or str(knowledge.get("providerScope") or "") != "provider_specific":
            return False
        if norm_provider(knowledge.get("provider")) != wanted:
            return False

    req_is_vendor = req_family in ("veeam_vbr", "vmware") or is_vendor_diagnostic_code(req_id)
    row_is_vendor = row_family in ("veeam_vbr", "vmware") or is_vendor_diagnostic_code(row_diag)
    if req_is_vendor or row_is_vendor:
        return req_is_vendor and row_is_vendor and row_diag == req_id

    if row_diag == req_id:
        return True

    # Cross-identity retrieval is permitted only for an explicitly approved entry
    # in the same family and within the configured semantic-distance threshold.
    return distance <= max_distance


async def search_similar_logs(
    db: AsyncSession,
    description: str,
    api_key: str | None = None,
    event_id: str | None = None,
    top_k: int = 2,
    source_family: str | None = None,
    diagnostic_code: str | None = None,
    provider: str | None = None,
) -> list[dict]:
    """Search only explicitly approved knowledge entries with domain guardrails.

    User feedback ranks helpfulness but never approves a candidate. Unknown sources
    perform no retrieval, and vendor diagnostics require the exact same code.
    """
    if settings.AUTH_MODE.lower() == 'secure':
        return []  # same ownership boundary as add_solution: the shared vector namespace is closed in secure mode
    family = source_family or ""
    identity = str(diagnostic_code or event_id or "")

    if family == "unknown_text":
        return []

    query_text = redact_for_embedding(f"Event ID: {identity}. Description: {description}")
    try:
        import asyncio
        embedding = await asyncio.to_thread(_get_embedding, query_text, api_key)
    except Exception:
        embedding = _get_embedding(query_text, api_key)

    if not embedding:
        return []
        
    try:
        distance_col = VectorKnowledge.embedding.cosine_distance(embedding)
        query = select(VectorKnowledge, distance_col.label("dist"))
        if diagnostic_code and is_vendor_diagnostic_code(diagnostic_code):
            # Exact diagnostic identity: the only safe cross-check.
            query = query.filter(VectorKnowledge.event_id == str(diagnostic_code))
        elif event_id and event_id != "Unknown":
            query = query.filter(VectorKnowledge.event_id == str(event_id))
        # Review approval gates retrieval; feedback score only ranks usefulness.
        query = (
            query.order_by(desc(VectorKnowledge.feedback_score), distance_col)
            .limit(max(top_k * 4, 8) if family not in PROVIDER_BEARING_FAMILIES else max(top_k * 25, 50))
        )
        rows = (await db.execute(query)).all()

        matches = []
        for row in rows:
            entity = row[0] if isinstance(row, (tuple, list)) else row
            try:
                distance = float(row[1]) if isinstance(row, (tuple, list)) else 0.0
            except (TypeError, ValueError, IndexError):
                distance = 0.0
            if not _is_usable_knowledge_row(
                getattr(entity, "event_id", ""),
                getattr(entity, "feedback_score", 0),
                identity,
                family,
                distance,
                row_solution_json=getattr(entity, "solution_json", None),
                request_provider=provider,
            ):
                continue
            if getattr(entity, "solution_json", None):
                public_solution = dict(entity.solution_json)
                public_solution.pop("_knowledge", None)
                matches.append(public_solution)
            if len(matches) >= top_k:
                break
        return matches
    except Exception as e:
        print(f"Vector search failed: {e}")
        return []
