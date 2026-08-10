import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyze, history, stats, auth, feedback, obsidian, admin
from app.core.database import engine, Base

load_dotenv()
import app.models.vector
import app.models.user

Base.metadata.create_all(bind=engine)

from app.core.auth import seed_users
seed_users()

app = FastAPI(
    title="EventIQ API",
    description="AI-powered Windows Event Log Analyzer API",
    version="1.0.0",
    redirect_slashes=False,
)

cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
allowed_origins = [o.strip() for o in cors_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(analyze.router, prefix="/api/v1/analyze", tags=["Analyze"])
app.include_router(history.router, prefix="/api/v1/history", tags=["History"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Stats"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(obsidian.router, prefix="/api/v1/obsidian", tags=["Obsidian"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])



@app.get("/")
def read_root():
    return {"message": "Welcome to EventIQ API"}
