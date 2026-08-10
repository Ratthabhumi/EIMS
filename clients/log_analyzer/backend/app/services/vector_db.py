import json
import requests
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.vector import VectorKnowledge

def _get_embedding(text_content: str, api_key: str) -> list[float]:
    if not api_key:
        return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    payload = {
        "model": "models/text-embedding-004",
        "content": {
            "parts": [{"text": text_content}]
        }
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "embedding" in data and "values" in data["embedding"]:
            return data["embedding"]["values"]
    except Exception as e:
        print(f"Failed to get embedding: {e}")
    return []

def add_solution(db: Session, event_id: str, description: str, solution_summary: dict, feedback_score: int, api_key: str):
    """Adds a log and its correct solution to the vector database."""
    if feedback_score < 0:
        return
        
    document_text = f"Event ID: {event_id}. Description: {description}"
    embedding = _get_embedding(document_text, api_key)
    
    if not embedding:
        return
        
    # Check if we already have this exact solution
    existing = db.query(VectorKnowledge).filter(VectorKnowledge.event_id == str(event_id), VectorKnowledge.description == description).first()
    if existing:
        existing.feedback_score = feedback_score
        existing.solution_json = solution_summary
    else:
        new_knowledge = VectorKnowledge(
            event_id=str(event_id),
            description=description,
            embedding=embedding,
            solution_json=solution_summary,
            feedback_score=feedback_score
        )
        db.add(new_knowledge)
    db.commit()

def search_similar_logs(db: Session, description: str, api_key: str, event_id: str = None, top_k: int = 2) -> list[dict]:
    """Search for past similar logs that were successfully solved."""
    if not api_key:
        return []
        
    embedding = _get_embedding(description, api_key)
    if not embedding:
        return []
        
    query = db.query(VectorKnowledge)
    if event_id:
        query = query.filter(VectorKnowledge.event_id == str(event_id))
        
    # Order by cosine distance (<=>)
    results = query.order_by(VectorKnowledge.embedding.cosine_distance(embedding)).limit(top_k).all()
    
    matches = []
    for row in results:
        matches.append(row.solution_json)
    return matches
