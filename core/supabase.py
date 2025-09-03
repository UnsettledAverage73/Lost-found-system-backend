from supabase import create_client, Client
import os
from dotenv import load_dotenv
from typing import Optional
from fastapi import HTTPException

# Load environment variables
load_dotenv(dotenv_path="backend/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None

def initialize_supabase_client():
    global supabase
    if SUPABASE_URL is None or SUPABASE_KEY is None:
        raise ValueError("Supabase URL or Key not found in environment variables.")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Supabase client initialized.")

def get_supabase_client():
    if supabase is None:
        raise ValueError("Supabase client not initialized. Call initialize_supabase_client() first.")
    return supabase

async def upload_file_to_supabase_storage(bucket_name: str, file_path: str, file_bytes: bytes, content_type: str) -> str:
    """Uploads a file to Supabase Storage and returns its public URL."""
    if supabase is None:
        raise ValueError("Supabase client not initialized.")
    
    try:
        # Supabase storage upload returns a dictionary with 'path' and other info
        response = supabase.storage.from_(bucket_name).upload(file_path, file_bytes, {"content-type": content_type})
        
        if response.data and "path" in response.data:
            # Construct the public URL. This assumes the bucket is public.
            # If private, you'd need to generate a signed URL.
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{response.data['path']}"
            return public_url
        else:
            # Handle error, response.error might contain details
            error_message = response.error.message if response.error else "Unknown upload error"
            print(f"Error uploading file to Supabase Storage: {error_message}")
            raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {error_message}")
    except Exception as e:
        print(f"Exception during file upload to Supabase Storage: {e}")
        raise HTTPException(status_code=500, detail=f"Exception during file upload: {e}")

async def get_file_from_supabase_storage(bucket_name: str, file_path: str) -> Optional[bytes]:
    """Retrieves file data (bytes) from Supabase Storage given its path."""
    if supabase is None:
        raise ValueError("Supabase client not initialized.")
    
    try:
        response = supabase.storage.from_(bucket_name).download(file_path)
        # If download is successful, response is bytes
        return response
    except Exception as e:
        print(f"Error retrieving file {file_path} from Supabase Storage: {e}")
        return None

# You can add more helper functions here for common Supabase operations (e.g., storage, auth)
