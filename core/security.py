from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from dotenv import load_dotenv
import os

# from fastapi import Depends, HTTPException, status # No longer needed for custom JWT
# from fastapi.security import OAuth2PasswordBearer # No longer needed for custom JWT

# Load environment variables for security module
load_dotenv(dotenv_path="backend/.env")

# SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key") # Removed custom JWT secret
# ALGORITHM = os.getenv("ALGORITHM", "HS256") # Removed custom JWT algorithm
# ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)) # Removed custom JWT expiration

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token") # Removed custom OAuth2 scheme

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Removed custom JWT token creation and decoding functions:
# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
#     ...
# def decode_access_token(token: str) -> Optional[dict]:
#     ...
# async def get_current_user(token: str = Depends(oauth2_scheme)):
#     ...
