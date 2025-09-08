from fastapi import APIRouter, Depends, HTTPException, status, Header, Form
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Optional, Annotated                                                                                                                                                                                                                                                                                                                                                          
from pydantic import BaseModel # Added BaseModel import
from fastapi.responses import JSONResponse # Import JSONResponse for setting cookies
from fastapi import Request # Import Request for checking hostname

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
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), database: MongoClient = Depends(get_database)):
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

    response = JSONResponse(content={"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token})
    
    is_local = request.url.hostname == "localhost"

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax" if is_local else "lax", # Set to lax for local development
        secure=False if is_local else True, # Set to False for local development (non-HTTPS)
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60, # max_age in seconds
        expires=refresh_token_expires, # expires in seconds (datetime.timedelta)
        path="/auth/refresh", # Accessible only from /auth/refresh
        domain=None, # Let browser manage domain for localhost
    )
    return response

@router.post("/auth/refresh", response_model=Token)
async def refresh_access_token(
    request: Request,
    refresh_token_cookie: Annotated[str | None, Header(alias="Cookie")] = None,
    refresh_token_header: Annotated[str | None, Header(alias="X-Refresh-Token")] = None, # Re-add custom header for local dev fallback
    database: MongoClient = Depends(get_database)
):
    is_local = request.url.hostname == "localhost"
    
    # Add debug prints to see raw headers
    print(f"[Backend Debug] Refresh Request - Raw Cookie Header: {refresh_token_cookie}")
    print(f"[Backend Debug] Refresh Request - X-Refresh-Token Header: {refresh_token_header}")
    
    refresh_token_value = None
    # 1. Try to get from HttpOnly cookie (primary method)
    if refresh_token_cookie:
        for cookie_pair in refresh_token_cookie.split('; '):
            if cookie_pair.strip().startswith('refresh_token='):
                refresh_token_value = cookie_pair.strip().split('=', 1)[1]
                print(f"[Backend Debug] Extracted refresh_token from cookie: {refresh_token_value[:10]}...")
                break
    
    # 2. Fallback to custom header for local development if cookie not found
    if not refresh_token_value and is_local and refresh_token_header:
        refresh_token_value = refresh_token_header
        print(f"[Backend Debug] Extracted refresh_token from X-Refresh-Token header (local dev fallback): {refresh_token_value[:10]}...")
    
    if not refresh_token_value:
        print("[Backend Debug] No refresh token found from cookie or header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_refresh_token(refresh_token_value)
    if payload is None:
        print("[Backend Debug] Invalid refresh token: payload is None.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    contact: str = payload.get("sub")
    if contact is None:
        print("[Backend Debug] Invalid refresh token payload: no 'sub' field.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user(contact, database)
    if not user or not user.hashed_refresh_token or not verify_password(refresh_token_value, user.hashed_refresh_token):
        print("[Backend Debug] Validation failed: User not found, no hashed token, or token mismatch.")
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

    # Issue a new refresh token (rotate refresh tokens)
    new_refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    new_refresh_token = create_refresh_token(
        data={"sub": user.contact}, expires_delta=new_refresh_token_expires
    )
    hashed_new_refresh_token = get_password_hash(new_refresh_token)

    await database["users"].update_one(
        {"_id": ObjectId(user.id)},
        {"$set": {"hashed_refresh_token": hashed_new_refresh_token}}
    )

    response = JSONResponse(content={"access_token": new_access_token, "token_type": "bearer", "refresh_token": new_refresh_token})
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="lax" if is_local else "lax", # Set to lax for local development
        secure=False if is_local else True, # Set to False for local development (non-HTTPS)
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        expires=new_refresh_token_expires,
        path="/auth/refresh", # Accessible only from /auth/refresh
        domain=None, # Let browser manage domain for localhost
    )
    return response

@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_user(
    request: Request, # Add Request to get hostname
    refresh_token_cookie: Annotated[str | None, Header(alias="Cookie")] = None,
    refresh_token_header: Annotated[str | None, Header(alias="X-Refresh-Token")] = None, # Re-add custom header for local dev fallback
    database: MongoClient = Depends(get_database),
):
    is_local = request.url.hostname == "localhost"
    
    refresh_token = None
    if refresh_token_cookie:
        for cookie_pair in refresh_token_cookie.split('; '):
            if cookie_pair.strip().startswith('refresh_token='):
                refresh_token = cookie_pair.strip().split('=', 1)[1]
                break
    
    # Fallback to custom header for local development if cookie not found
    if not refresh_token and is_local and refresh_token_header:
        refresh_token = refresh_token_header
        print(f"[Backend Debug] Logout: Extracted refresh_token from X-Refresh-Token header (local dev fallback): {refresh_token[:10]}...")

    if refresh_token:
        payload = decode_refresh_token(refresh_token)
        if payload and "sub" in payload:
            contact: str = payload["sub"]
            user = await get_user(contact, database)
            if user and user.hashed_refresh_token and verify_password(refresh_token, user.hashed_refresh_token):
                # Invalidate refresh token by removing it from the database
                await database["users"].update_one(
                    {"_id": ObjectId(user.id)},
                    {"$set": {"hashed_refresh_token": None}}
                )
    
    response = JSONResponse(content={})
    
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        samesite="lax" if is_local else "lax", # Set to lax for local development
        secure=False if is_local else True, # Set to False for local development (non-HTTPS)
        path="/auth/refresh", # Make sure to delete the cookie from the correct path
        domain=None, # Let browser manage domain for localhost
    )
    return response

@router.post("/auth/set-refresh-cookie", status_code=status.HTTP_204_NO_CONTENT) # New endpoint to explicitly set refresh cookie
async def set_refresh_cookie(
    request: Request,
    refresh_token: Annotated[str, Form()],
    database: MongoClient = Depends(get_database)
):
    is_local = request.url.hostname == "localhost"
    
    response = JSONResponse(content={})
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax" if is_local else "lax", # Set to lax for local development
        secure=False if is_local else True, # Set to False for local development (non-HTTPS)
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60, # max_age in seconds
        path="/auth/refresh", # Accessible only from /auth/refresh
        domain=None, # Let browser manage domain for localhost
    )
    return response

@router.get("/auth/me", response_model=UserSchema)
async def read_users_me(current_user: UserSchema = Depends(get_current_user)):
    return current_user
