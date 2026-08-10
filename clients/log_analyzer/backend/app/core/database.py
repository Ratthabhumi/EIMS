import os

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./history.db")
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _ensure_schema():
    Base.metadata.create_all(bind=engine)
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        return
    with engine.connect() as conn:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(analysis_history)")).fetchall()
        }
        if columns and "solution_summary" not in columns:
            conn.execute(text("ALTER TABLE analysis_history ADD COLUMN solution_summary JSON"))
            conn.commit()
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(analysis_history)")).fetchall()
        }
        if columns and "event_metadata" not in columns:
            conn.execute(text("ALTER TABLE analysis_history ADD COLUMN event_metadata JSON"))
            conn.commit()
        if columns and "username" not in columns:
            conn.execute(text("ALTER TABLE analysis_history ADD COLUMN username TEXT DEFAULT 'admin'"))
            conn.commit()
        if columns and "feedback_by" not in columns:
            conn.execute(text("ALTER TABLE analysis_history ADD COLUMN feedback_by TEXT"))
            conn.commit()


_ensure_schema()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
