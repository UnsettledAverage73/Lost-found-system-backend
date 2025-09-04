from fastapi import APIRouter, Depends, HTTPException, status, Header, Form
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Optional, Annotated
from pydantic import BaseModel # Added BaseModel import

from models.schemas import UserSchema, UserRegisterSchema, PyObjectId # Re-added PyObjectId
from core.database import get_database # Re-added MongoDB database import
from core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES # Re-added custom JWT creation
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
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UserSchema)
async def read_users_me(current_user: UserSchema = Depends(get_current_user)):
    return current_user
