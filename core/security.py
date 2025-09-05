from datetime import datetime, timedelta, timezone
from typing import Optional
import os
from dotenv import load_dotenv

from jose import JWTError, jwt # Re-added jose imports for JWT
from passlib.context import CryptContext

from models.schemas import UserSchema # Import UserSchema for token validation
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # Re-added OAuth2PasswordBearer
from core.database import get_database
from pymongo import MongoClient

# Load environment variables
load_dotenv(dotenv_path="backend/.env")

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key") # Re-added SECRET_KEY
ALGORITHM = os.getenv("ALGORITHM", "HS256") # Re-added ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)) # Re-added ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", 7 * 24 * 60)) # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token") # Re-added OAuth2 scheme

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Re-added JWT functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def decode_refresh_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme), database: MongoClient = Depends(get_database)) -> UserSchema:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    contact: str = payload.get("sub")
    user_role: str = payload.get("role")
    if contact is None or user_role is None:
        raise credentials_exception
    
    # Retrieve user from MongoDB based on contact
    user_data = await database["users"].find_one({"contact": contact})
    if user_data is None:
        raise credentials_exception
    
    return UserSchema.model_validate(user_data)
