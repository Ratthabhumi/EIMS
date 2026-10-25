"""Revocable user sessions and bounded login windows; no raw JWT/password storage."""
from sqlalchemy import Column, DateTime, Integer, String
from backend.infrastructure.database import Base


class AnalyzerSession(Base):
    __tablename__ = 'analyzer_sessions'
    id = Column(String(64), primary_key=True)  # SHA-256 of a random signed sid
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String, nullable=False)
    credential_version = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class LoginWindow(Base):
    __tablename__ = 'analyzer_login_windows'
    id = Column(String(64), primary_key=True)  # hashed scope, no submitted username
    attempts = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
