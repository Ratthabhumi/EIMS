from sqlalchemy.future import select
import json
import re
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, text
from backend.domain.analyzer.models.vector import VectorKnowledge
from backend.domain.analyzer.services.vendor_parsers import is_vendor_diagnostic_code

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

def _get_embedding(text_content: str, api_key: Optional[str] = None) -> list[float]:
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

    # 2. Fallback: Cloud Gemini API if model cannot be loaded and key is present
    if api_key:
        import requests
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": text_content}]}
        }
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "embedding" in data and "values" in data["embedding"]:
                return data["embedding"]["values"][:384]
        except Exception as e:
            print(f"Cloud Gemini embedding error: {e}")

    return []

async def add_solution(
    db: AsyncSession, 
    event_id: str, 
    description: str, 
    solution_summary: dict, 
    feedback_score: int = 0, 
    api_key: Optional[str] = None
):
    """Adds a log and its verified solution to the Vector Knowledge Base.

    Negative feedback no longer vanishes: the exact existing row is
    updated/quarantined with the negative score so retrieval guardrails
    exclude it.  When no exact row exists there is nothing to quarantine
    and nothing is inserted.
    """
    try:
        # Check if we already have this exact solution
        existing = (await db.execute(select(VectorKnowledge).filter(VectorKnowledge.event_id == str(event_id), VectorKnowledge.description == description))).scalars().first()
    except Exception as e:
        print(f"Failed to look up Vector DB row: {e}")
        if feedback_score < 0:
            return
        existing = None

    if existing is not None:
        # Quarantine path: a thumbs-down lands here and the row becomes
        # non-retrievable via the feedback_score guardrail below.
        existing.feedback_score = feedback_score
        if solution_summary:
            existing.solution_json = solution_summary
        if feedback_score >= 0:
            refresh_text = redact_for_embedding(f"Event ID: {event_id}. Description: {description}")
            try:
                import asyncio
                refresh_embedding = await asyncio.to_thread(_get_embedding, refresh_text, api_key)
            except Exception:
                refresh_embedding = _get_embedding(refresh_text, api_key)
            if refresh_embedding:
                existing.embedding = refresh_embedding
        try:
            await db.commit()
        except Exception as e:
            print(f"Failed to update Vector DB row: {e}")
            await db.rollback()
        return

    if feedback_score < 0:
        # Nothing to quarantine: no exact row exists, so insert nothing.
        return

    document_text = redact_for_embedding(f"Event ID: {event_id}. Description: {description}")
    try:
        import asyncio
        embedding = await asyncio.to_thread(_get_embedding, document_text, api_key)
    except Exception:
        embedding = _get_embedding(document_text, api_key)
    
    if not embedding:
        return
        
    try:
        new_knowledge = VectorKnowledge(
            event_id=str(event_id),
            description=description,
            embedding=embedding,
            solution_json=solution_summary,
            feedback_score=feedback_score
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
) -> bool:
    """Pure retrieval-guardrail predicate (unit-testable, no DB).

    Rules:
    - negative feedback rows are never retrievable;
    - vendor diagnostic requests reuse ONLY the exact same code
      (Windows solutions can never answer Veeam/VMware and vice versa);
    - unverified score-0 rows are reusable ONLY under the exact same
      diagnostic identity;
    - cross-identity reuse additionally requires a close vector distance.
    """
    try:
        score = int(row_score) if row_score is not None else 0
    except (TypeError, ValueError):
        score = 0
    if score < 0:
        return False

    if (request_family or "") == "unknown_text":
        # Unidentified sources never reuse cross-domain knowledge.
        return False

    row_id = str(row_event_id or "")
    req = str(request_identity or "")
    req_is_vendor = is_vendor_diagnostic_code(req)
    row_is_vendor = is_vendor_diagnostic_code(row_id)

    if req_is_vendor:
        return row_id == req
    if row_is_vendor:
        # A vendor solution must never answer a non-vendor request.
        return False

    if not req or req == "Unknown":
        # No diagnostic identity: only positively verified rows, gated.
        if score <= 0:
            return False
        return distance <= max_distance

    if row_id == req:
        return True
    # Cross-identity: verified rows only, and only when genuinely close.
    if score <= 0:
        return False
    return distance <= max_distance


async def search_similar_logs(
    db: AsyncSession, 
    description: str, 
    api_key: Optional[str] = None, 
    event_id: Optional[str] = None, 
    top_k: int = 2,
    source_family: Optional[str] = None,
    diagnostic_code: Optional[str] = None,
) -> List[dict]:
    """Search past solved logs with domain guardrails.

    - unknown_text sources perform NO retrieval (no cross-domain answers);
    - vendor diagnostic codes filter to the exact identity;
    - negative-feedback rows are excluded; score-0 rows only under the
      same diagnostic identity; verified rows are preferred.
    """
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
        # Prefer positively verified knowledge, then closest vectors.
        query = (
            query.order_by(desc(VectorKnowledge.feedback_score), distance_col)
            .limit(max(top_k * 4, 8))
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
            ):
                continue
            if getattr(entity, "solution_json", None):
                matches.append(entity.solution_json)
            if len(matches) >= top_k:
                break
        return matches
    except Exception as e:
        print(f"Vector search failed: {e}")
        return []
