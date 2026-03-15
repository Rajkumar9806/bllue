"""
Arrow Backend - Authentication Services
JWT, OTP, Password Hashing
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import random
import string

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User, OTPCode

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    return user


def generate_otp(length: int = 6) -> str:
    """Generate random OTP code"""
    return ''.join(random.choices(string.digits, k=length))


def generate_invite_code(length: int = 8) -> str:
    """Generate random invite code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


async def create_otp(db: AsyncSession, phone_number: str) -> str:
    """Create and store OTP code"""
    # Invalidate existing OTPs for this phone
    existing = await db.execute(
        select(OTPCode).where(
            OTPCode.phone_number == phone_number,
            OTPCode.is_used == False
        )
    )
    for otp in existing.scalars():
        otp.is_used = True
    
    # Create new OTP
    code = generate_otp()
    otp = OTPCode(
        phone_number=phone_number,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(otp)
    await db.commit()
    
    return code


async def verify_otp(db: AsyncSession, phone_number: str, code: str) -> bool:
    """Verify OTP code"""
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.phone_number == phone_number,
            OTPCode.code == code,
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow()
        )
    )
    otp = result.scalar_one_or_none()
    
    if otp is None:
        return False
    
    # Mark as used
    otp.is_used = True
    await db.commit()
    
    return True
