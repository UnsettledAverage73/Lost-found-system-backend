from fastapi import APIRouter, Depends, HTTPException, status, Header, Form
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Optional, Annotated
from pydantic import BaseModel # Added BaseModel import
from fastapi.responses import JSONResponse # Import JSONResponse for setting cookies

from models.schemas import UserSchema, UserRegisterSchema, PyObjectId # Re-added PyObjectId
from core.database import get_database # Re-added MongoDB database import
from core.security import (
    verify_password, get_password_hash,
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
    create_refresh_token, REFRESH_TOKEN_EXPIRE_MINUTES, decode_refresh_token
)
from bson import ObjectId # Re-added MongoDB ObjectId import
from core.security import get_current_user # Re-added custom JWT current user
from pymongo import MongoClient # Re-added MongoDB client import

# from core.supabase import get_supabase_client # Removed Supabase imports
# from supabase import Client # Removed Client

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserInDB(UserSchema):
    hashed_password: str

async def get_user(contact: str, database: MongoClient) -> Optional[UserInDB]:
    user_data = await database["users"].find_one({"contact": contact})
    if user_data:
        return UserInDB(**user_data, id=str(user_data["_id"]))
    return None

async def authenticate_user(contact: str, password: str, database: MongoClient) -> Optional[UserSchema]:
    user = await get_user(contact, database)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


@router.post("/auth/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserRegisterSchema, database: MongoClient = Depends(get_database)):
    existing_user = await database["users"].find_one({"contact": user_in.contact})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contact already registered"
        )
    
    hashed_password = get_password_hash(user_in.password)
    user_data = user_in.model_dump()
    user_data["hashed_password"] = hashed_password
    del user_data["password"] # Remove plain password before saving
    
    new_user = await database["users"].insert_one(user_data)
    created_user = await database["users"].find_one({"_id": new_user.inserted_id})
    return UserSchema.model_validate(created_user)

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), database: MongoClient = Depends(get_database)):
    user = await authenticate_user(form_data.username, form_data.password, database)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.contact, "role": user.role}, expires_delta=access_token_expires
    )

    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_refresh_token(
        data={"sub": user.contact}, expires_delta=refresh_token_expires
    )

    # Hash the refresh token before storing in DB
    hashed_refresh_token = get_password_hash(refresh_token) # Re-use password hash function for simplicity

    # Store hashed refresh token in user's document
    await database["users"].update_one(
        {"_id": ObjectId(user.id)}, # Use ObjectId for _id
        {"$set": {"hashed_refresh_token": hashed_refresh_token}}
    )

    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax", # "strict" or "lax" for security
        secure=True, # Ensure this is True in production with HTTPS
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60, # max_age in seconds
        expires=refresh_token_expires, # expires in seconds (datetime.timedelta)
        path="/", # Accessible from all paths
    )
    return response

@router.post("/auth/refresh", response_model=Token)
async def refresh_access_token(
    refresh_token: Annotated[str | None, Header(alias="Refresh-Token")] = None, # Expect refresh token in header if not in cookie
    refresh_token_cookie: Annotated[str | None, Header(alias="Cookie")] = None, # Try to get from Cookie header
    database: MongoClient = Depends(get_database)
):
    token = refresh_token # Prefer header, then try parsing cookie
    if not token and refresh_token_cookie:
        # Parse refresh_token from the Cookie header string
        for cookie_pair in refresh_token_cookie.split('; '):
            if cookie_pair.startswith('refresh_token='):
                token = cookie_pair.split('=', 1)[1]
                break

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_refresh_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    contact: str = payload.get("sub")
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user(contact, database)
    if not user or not user.hashed_refresh_token or not verify_password(token, user.hashed_refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": user.contact, "role": user.role}, expires_delta=access_token_expires
    )

    # Optionally, issue a new refresh token (rotate refresh tokens)
    new_refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    new_refresh_token = create_refresh_token(
        data={"sub": user.contact}, expires_delta=new_refresh_token_expires
    )
    hashed_new_refresh_token = get_password_hash(new_refresh_token)

    await database["users"].update_one(
        {"_id": ObjectId(user.id)},
        {"$set": {"hashed_refresh_token": hashed_new_refresh_token}}
    )

    response = JSONResponse(content={"access_token": new_access_token, "token_type": "bearer"})
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="lax",
        secure=True, # Ensure True in production with HTTPS
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        expires=new_refresh_token_expires,
        path="/",
    )
    return response

@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(current_user: UserSchema = Depends(get_current_user), database: MongoClient = Depends(get_database)):
    # Invalidate refresh token by removing it from the database
    await database["users"].update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"hashed_refresh_token": None}}
    )
    # Clear the HttpOnly cookie from the client
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax", secure=True, path="/")
    return response

@router.get("/auth/me", response_model=UserSchema)
async def read_users_me(current_user: UserSchema = Depends(get_current_user)):
    return current_user
