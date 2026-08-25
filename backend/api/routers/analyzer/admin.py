from sqlalchemy.future import select
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from pydantic import BaseModel
from typing import List

from backend.infrastructure.database import get_db_session as get_db
from backend.domain.analyzer.auth import get_current_user, get_user_role
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.models.history import AnalysisHistory

router = APIRouter()

async def require_admin(username: str = Depends(get_current_user)):
    role = get_user_role(username)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return username

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"

class UserResponse(BaseModel):
    id: int
    username: str
    role: str

class LeaderboardEntry(BaseModel):
    username: str
    analyses_count: int

@router.get("/users", response_model=List[UserResponse])
async def get_users(db: AsyncSession = Depends(get_db), _: str = Depends(require_admin)):
    users = (await db.execute(select(User))).scalars().all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

@router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db), _: str = Depends(require_admin)):
    existing = (await db.execute(select(User).filter(User.username == user.username))).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = User(username=user.username, password=user.password, role=user.role)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"id": new_user.id, "username": new_user.username, "role": new_user.role}

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), current_admin: str = Depends(require_admin)):
    user = (await db.execute(select(User).filter(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.username == current_admin:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    db.delete(user)
    await db.commit()
    return {"status": "success", "message": "User deleted"}

@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(db: AsyncSession = Depends(get_db), _: str = Depends(require_admin)):
    # Group by username and count
    results = db.query(
        AnalysisHistory.username, 
        func.count(AnalysisHistory.id).label('total')
    ).group_by(AnalysisHistory.username).order_by(func.count(AnalysisHistory.id).desc()).all()
    
    return [{"username": r[0] or "Unknown", "analyses_count": r[1]} for r in results]
