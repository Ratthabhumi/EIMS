from sqlalchemy import Boolean, Column, Integer, String
from backend.infrastructure.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String, default="user")
    # Additive capability: a reviewer remains a full Engineer user.
    knowledge_reviewer = Column(Boolean, nullable=False, default=False, server_default="false")
