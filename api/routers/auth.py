from fastapi import APIRouter, Depends, HTTPException, status, Header, Form
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Optional, Annotated
from pydantic import BaseModel # Added BaseModel import

from backend.models.schemas import UserSchema
# from backend.core.database import get_database # Removed MongoDB database import
from backend.core.security import verify_password, get_password_hash # Keep for now if we plan to store hashed passwords in Supabase table for additional user data
# from backend.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES # Removed custom JWT creation
# from bson import ObjectId # Removed MongoDB ObjectId import
# from backend.core.security import get_current_user # Removed custom JWT current user
from backend.core.supabase import get_supabase_client
from supabase import Client
from backend.models.schemas import UserRegisterSchema

router = APIRouter()

class Token(BaseModel): # Changed to inherit directly from BaseModel
    access_token: str
    token_type: str = "bearer"
    # We might need to adjust this based on what Supabase returns and what frontend expects

# UserInDB class is no longer needed if we rely on Supabase's auth system entirely
# class UserInDB(UserSchema):
#     hashed_password: str

# get_user and authenticate_user functions are replaced by Supabase auth methods
# async def get_user(email: str, database: MongoClient) -> Optional[UserInDB]:
#     user_data = await database["users"].find_one({"contact": email})
#     if user_data:
#         return UserInDB(**user_data, id=str(user_data["_id"]))
#     return None

# async def authenticate_user(email: str, password: str, database: MongoClient) -> Optional[UserSchema]:
#     user = await get_user(email, database)
#     if not user:
#         return None
#     if not verify_password(password, user.hashed_password):
#         return None
#     return user

async def get_current_active_user(supabase: Client = Depends(get_supabase_client), authorization: str = Header(...)) -> UserSchema:
    token = authorization.split(" ")[1] if " " in authorization and authorization.startswith("Bearer ") else authorization
    if not token:
        print("Authorization header missing or malformed.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing or malformed.")
    try:
        # Explicitly check for an existing session before calling get_user
        # This can sometimes provide better error context
        # user_response = supabase.auth.get_user(token)
        # Using set_session and then get_user might be more robust for token validation
        # However, get_user(jwt) is the direct way to validate a JWT without setting a session client-side
        # Let's stick to get_user(jwt) but be more verbose in logging.

        user_response = supabase.auth.get_user(token)

        print(f"Supabase get_user response: {user_response}")

        if user_response and user_response.user:
            # Fetch additional user profile data from 'profiles' table
            # Assuming 'profiles' table has columns like 'id', 'role', 'contact', 'consent_face_qr'
            profile_response = supabase.from_("profiles").select("id, role, contact, consent_face_qr").eq("id", user_response.user.id).single().execute()
            if profile_response.data:
                return UserSchema(
                    id=profile_response.data["id"],
                    role=profile_response.data["role"],
                    contact=profile_response.data["contact"],
                    consent_face_qr=profile_response.data["consent_face_qr"]
                )
            else:
                # If no profile data, create a default one (e.g., for new users from external providers)
                new_profile = {
                    "id": user_response.user.id,
                    "role": "VOLUNTEER", # Default role
                    "contact": user_response.user.email, # Or phone if available
                    "consent_face_qr": False
                }
                insert_response = supabase.from_("profiles").insert([new_profile]).execute()
                if insert_response.data:
                    return UserSchema(**new_profile)
                else:
                    print(f"Error creating profile for user {user_response.user.id}: {insert_response.last_error}")
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create user profile")
        elif user_response and user_response.error:
            print(f"Supabase get_user failed with error: {user_response.error.message}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=user_response.error.message)
        else:
            print("Supabase get_user failed: No user or explicit error.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    except Exception as e:
        print(f"Exception during get_current_active_user: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")


@router.post("/auth/register", response_model=UserSchema)
async def register_user(user_in: UserRegisterSchema, supabase: Client = Depends(get_supabase_client)):
    try:
        # Check if user already exists in Supabase Auth
        # Supabase sign_up handles existing email by not creating a new user but returning the existing user's data if email_confirm is false.
        # For strict unique email check, you might need to query the 'profiles' table first.
        existing_user_response = supabase.from_("profiles").select("id").eq("contact", user_in.contact).execute()
        if existing_user_response.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        # Register user in Supabase Auth
        auth_response = supabase.auth.sign_up({"email": user_in.contact, "password": user_in.password})

        if auth_response.user:
            # Insert additional user data into your 'profiles' table
            new_profile = {
                "id": auth_response.user.id, # Link profile to Supabase Auth user ID
                "role": user_in.role,
                "contact": user_in.contact,
                "consent_face_qr": user_in.consent_face_qr
            }
            profile_response = supabase.from_("profiles").insert([new_profile]).execute()

            if profile_response.data:
                return UserSchema(**new_profile)
            else:
                # If profile creation fails, consider rolling back user creation in Supabase Auth
                print(f"Error creating profile for user {auth_response.user.id}: {profile_response.last_error}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User registration failed: Could not create profile")
        else:
            print(f"Supabase Auth sign_up failed: {auth_response.last_error}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User registration failed")
    except Exception as e:
        print(f"Error during registration: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred: {e}")

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), supabase: Client = Depends(get_supabase_client)):
    try:
        auth_response = supabase.auth.sign_in_with_password({"email": form_data.username, "password": form_data.password})
        
        if auth_response.session:
            # Supabase returns an access token which is its JWT
            return {"access_token": auth_response.session.access_token, "token_type": "bearer"}
        elif auth_response.error:
            print(f"Supabase Auth sign_in_with_password failed: {auth_response.error.message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=auth_response.error.message, # Use Supabase's error message
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            # This case might happen if, for example, email confirmation is pending but no explicit error is returned
            print("Supabase Auth sign_in_with_password failed without explicit error or session.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password", # Fallback to generic message
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        print(f"Error during login: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

@router.get("/auth/me", response_model=UserSchema)
async def read_users_me(current_user: UserSchema = Depends(get_current_active_user)):
    return current_user
