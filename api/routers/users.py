from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional
# from pymongo import MongoClient # Removed MongoDB client import
# from bson import ObjectId # Removed MongoDB ObjectId import

from backend.models.schemas import UserSchema # Removed PyObjectId
# from backend.core.database import get_database # Removed MongoDB database import
from backend.core.supabase import get_supabase_client
from supabase import Client # Import Client for type hinting

router = APIRouter()

@router.post("/users", response_model=UserSchema)
async def create_or_update_user(user: UserSchema, supabase: Client = Depends(get_supabase_client)):
    """
    Creates or updates a user profile, including consent settings in Supabase.
    """
    user_dict = user.dict(by_alias=True, exclude_none=True)
    
    # Supabase doesn't have a direct upsert for insert(). We check if exists first.
    existing_user_response = supabase.from_("profiles").select("id").eq("id", user_dict["id"]).single().execute()

    if existing_user_response.data:
        # Update existing user
        response = supabase.from_("profiles").update(user_dict).eq("id", user_dict["id"]).execute()
        if not response.data:
            print(f"Supabase update failed: {response.last_error}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User update failed")
    else:
        # Create new user
        response = supabase.from_("profiles").insert([user_dict]).execute()
        if not response.data:
            print(f"Supabase insert failed: {response.last_error}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User creation failed")
    
    print(f"User {user.id} profile updated. Consent for Face/QR: {user.consent_face_qr}")
    return user

@router.get("/users/{user_id}", response_model=UserSchema)
async def get_user_profile(user_id: str, supabase: Client = Depends(get_supabase_client)):
    """
    Retrieves a user profile by ID from Supabase.
    """
    response = supabase.from_("profiles").select("*").eq("id", user_id).single().execute()
    user_data = response.data

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return UserSchema(**user_data)
