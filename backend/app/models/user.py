from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from app.database.core import Base
import enum
from app.core.config import settings

L = settings.limits

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(L.ID_MAX_LENGTH), primary_key=True, index=True)
    username = Column(String(L.ID_MAX_LENGTH), unique=True, index=True, nullable=False)
    hashed_password = Column(String(L.EMAIL_MAX_LENGTH), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.VIEWER, nullable=False)
    merchant_id = Column(String(L.ID_MAX_LENGTH), index=True, nullable=True) # Supports multi-tenancy
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
