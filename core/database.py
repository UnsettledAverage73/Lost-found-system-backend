# backend/core/database.py

import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from typing import Optional, Any
from bson import ObjectId
import io # Added import for io

# Load environment variables
load_dotenv(dotenv_path="backend/.env")

MONGO_DB_URL = os.getenv("MONGO_DB_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "lostfounddb")

client: Optional[AsyncIOMotorClient] = None
database: Optional[Any] = None # Motor collection type
fs: Optional[AsyncIOMotorGridFSBucket] = None

async def startup_db_client():
    global client, database, fs
    try:
        client = AsyncIOMotorClient(MONGO_DB_URL, serverSelectionTimeoutMS=5000)
        await client.admin.command('ping')
        database = client[MONGO_DB_NAME]
        fs = AsyncIOMotorGridFSBucket(database)
        print("Connected to MongoDB!")
    except ServerSelectionTimeoutError as err:
        print(f"MongoDB connection error: {err}")
        client = None
        database = None
        fs = None
        # Optionally, raise the exception or exit if DB is critical for startup
        raise

async def shutdown_db_client():
    global client
    if client:
        client.close()
        print("Disconnected from MongoDB.")

def get_database():
    if database is None:
        raise Exception("Database client not initialized. Call startup_db_client() first.")
    return database

def get_gridfs_bucket():
    if fs is None:
        raise Exception("GridFS bucket not initialized. Call startup_db_client() first.")
    return fs

async def store_image_in_gridfs(image_data: bytes, filename: str, content_type: str) -> str:
    """Stores image data in GridFS and returns the file ID."""
    bucket = get_gridfs_bucket()
    # Wrap image_data in BytesIO for upload_from_stream
    file_id = await bucket.upload_from_stream(
        filename,
        io.BytesIO(image_data), # Use io.BytesIO to create a stream from bytes
        metadata={"contentType": content_type}
    )
    return str(file_id) # Return as string for Pydantic

async def get_image_from_gridfs(file_id: str) -> Optional[bytes]:
    """Retrieves image data from GridFS given a file ID."""
    bucket = get_gridfs_bucket()
    try:
        # Convert string ID to ObjectId
        oid = ObjectId(file_id)
        # Use open_download_stream to read from GridFS
        file_cursor = await bucket.open_download_stream(oid)
        image_data = await file_cursor.read()
        await file_cursor.close()
        return image_data
    except Exception as e:
        print(f"Error retrieving image {file_id} from GridFS: {e}")
        return None
