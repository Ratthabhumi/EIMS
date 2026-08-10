from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.history import AnalysisHistory
from app.services.obsidian import save_to_obsidian

router = APIRouter()

class ObsidianRequest(BaseModel):
    history_id: int

@router.post("/obsidian/export")
def export_obsidian(req: ObsidianRequest, db: Session = Depends(get_db)):
    history_item = db.query(AnalysisHistory).filter(AnalysisHistory.id == req.history_id).first()
    if not history_item:
        raise HTTPException(status_code=404, detail="History not found")
        
    if not history_item.solution_summary:
        raise HTTPException(status_code=400, detail="No solution to export")
        
    try:
        path = save_to_obsidian(
            event_id=history_item.event_id,
            description=history_item.description,
            solution_summary=history_item.solution_summary
        )
        return {"status": "success", "filepath": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export to Obsidian: {e}")
