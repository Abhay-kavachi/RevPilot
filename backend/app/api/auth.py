import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database.core import get_db
from app.models.user import User, UserRole
from app.core.config import settings
import bcrypt
import hashlib

SECRET_KEY = settings.security.JWT_SECRET_KEY
ALGORITHM = settings.security.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.security.JWT_EXPIRY_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

def _prehash(password: str) -> bytes:
    # Hash password with SHA256 first, then base64 encode to bypass bcrypt 72-byte limit
    import base64
    return base64.b64encode(hashlib.sha256(password.encode('utf-8')).digest())

def verify_password(plain_password, hashed_password):
    prehashed = _prehash(plain_password)
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(prehashed, hashed_password)

def get_password_hash(password):
    prehashed = _prehash(password)
    # Use 12 rounds for bcrypt
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(prehashed, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def require_role(allowed_roles: list[UserRole]):
    def role_dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not enough privileges"
            )
        return current_user
    return role_dependency
