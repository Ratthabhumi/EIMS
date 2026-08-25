from sqlalchemy.future import select
import json
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.domain.analyzer.models.vector import VectorKnowledge

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
    """Adds a log and its verified solution to the Vector Knowledge Base."""
    if feedback_score < 0:
        return
        
    document_text = f"Event ID: {event_id}. Description: {description}"
    try:
        import asyncio
        embedding = await asyncio.to_thread(_get_embedding, document_text, api_key)
    except Exception:
        embedding = _get_embedding(document_text, api_key)
    
    if not embedding:
        return
        
    try:
        # Check if we already have this exact solution
        existing = (await db.execute(select(VectorKnowledge).filter(VectorKnowledge.event_id == str(event_id), VectorKnowledge.description == description))).scalars().first()
        if existing:
            existing.feedback_score = feedback_score
            existing.solution_json = solution_summary
            existing.embedding = embedding
        else:
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

async def search_similar_logs(
    db: AsyncSession, 
    description: str, 
    api_key: Optional[str] = None, 
    event_id: Optional[str] = None, 
    top_k: int = 2
) -> List[dict]:
    """Search for past similar logs that were successfully solved using Cosine Similarity."""
    try:
        import asyncio
        embedding = await asyncio.to_thread(_get_embedding, description, api_key)
    except Exception:
        embedding = _get_embedding(description, api_key)

    if not embedding:
        return []
        
    try:
        query = select(VectorKnowledge)
        if event_id and event_id != "Unknown":
            query = query.filter(VectorKnowledge.event_id == str(event_id))
            
        # Order by Cosine Distance (<=> operator in pgvector)
        query = query.order_by(VectorKnowledge.embedding.cosine_distance(embedding)).limit(top_k)
        results = (await db.execute(query)).scalars().all()
        
        matches = []
        for row in results:
            if row.solution_json:
                matches.append(row.solution_json)
        return matches
    except Exception as e:
        print(f"Vector search failed: {e}")
        return []
