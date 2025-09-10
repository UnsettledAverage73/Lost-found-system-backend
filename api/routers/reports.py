from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status, Query
from typing import List, Optional, Literal
import base64
import uuid # Import uuid for generating unique file names
from datetime import datetime # Added datetime import
import asyncio # Added asyncio import

from models.schemas import ReportSchema, PersonSchema, ItemSchema, PyObjectId # Re-added PyObjectId
from core.database import get_database, store_image_in_gridfs, get_image_from_gridfs # Re-added MongoDB database and GridFS imports
from ml.matcher import run_matching_job
# from ml.speech_to_text import transcribe_audio # Temporarily disabled speech-to-text functionality
from pymongo import MongoClient # Re-added MongoDB client import
from bson import ObjectId # Re-added MongoDB ObjectId import
from gridfs import GridFSBucket # Added GridFSBucket import

# from backend.core.supabase import get_supabase_client, upload_file_to_supabase_storage, get_file_from_supabase_storage # Removed Supabase imports
# from supabase import Client # Removed Client for type hinting

router = APIRouter()

# SUPABASE_REPORT_PHOTOS_BUCKET = "report_photos" # Removed Supabase bucket definition

def get_gridfs_bucket():
    """Helper function to get the GridFS bucket."""
    return GridFSBucket(get_database().client.gridfs_db)

@router.post("/reports/lost", response_model=ReportSchema)
async def create_lost_report(
    subject_type: Literal["PERSON", "ITEM"] = Form(..., alias="subject"),
    ref_ids_str: str = Form(..., alias="refs", description="Comma-separated IDs of person/item"),
    description_text: str = Form(..., alias="desc_text"),
    language: str = Form(..., alias="lang"),
    location: str = Form(...),
    photos: Optional[List[UploadFile]] = File(None), # Made photos optional
    database: MongoClient = Depends(get_database) # Reverted to MongoDB client dependency
):
    ref_ids = [rid.strip() for rid in ref_ids_str.split(',')]
    
    # Store photos in GridFS
    photo_ids = []
    if photos:
        for photo in photos:
            if photo.content_type not in ["image/jpeg", "image/png"]:
                raise HTTPException(status_code=400, detail="Only JPEG or PNG images are allowed.")
            image_data = await photo.read()
            # Generate a unique filename or use a simpler one if GridFS handles IDs
            filename = f"{uuid.uuid4()}-{photo.filename}"
            file_id = await store_image_in_gridfs(image_data, filename, photo.content_type)
            photo_ids.append(file_id)

    # Handle location field: convert dictionary to string if necessary
    if isinstance(location, dict):
        location_str = location.get("description", str(location))
    else:
        location_str = location

    report_data = {
        "type": "LOST",
        "subject": subject_type,
        "refs": ref_ids,
        "description_text": description_text,
        "language": language,
        "photo_ids": photo_ids, # Use GridFS IDs
        "location": location_str,
        "status": "OPEN",
        "created_at": datetime.utcnow()
    }
    
    # Insert into MongoDB
    new_report = await database["reports"].insert_one(report_data)
    created_report = await database["reports"].find_one({"_id": new_report.inserted_id})
    
    # Start matching process in the background
    asyncio.create_task(run_matching_job(str(new_report.inserted_id), created_report, database))
    
    return ReportSchema.model_validate(created_report)


@router.post("/reports/found", response_model=ReportSchema)
async def create_found_report(
    subject_type: Literal["PERSON", "ITEM"] = Form(..., alias="subject"),
    ref_ids_str: str = Form(..., alias="refs", description="Comma-separated IDs of person/item"),
    description_text: str = Form(..., alias="desc_text"),
    language: str = Form(..., alias="lang"),
    location: str = Form(...),
    photos: Optional[List[UploadFile]] = File(None), # Made photos optional
    database: MongoClient = Depends(get_database) # Reverted to MongoDB client dependency
):
    ref_ids = [rid.strip() for rid in ref_ids_str.split(',')]

    # Store photos in GridFS
    photo_ids = []
    if photos:
        for photo in photos:
            if photo.content_type not in ["image/jpeg", "image/png"]:
                raise HTTPException(status_code=400, detail="Only JPEG or PNG images are allowed.")
            image_data = await photo.read()
            filename = f"{uuid.uuid4()}-{photo.filename}"
            file_id = await store_image_in_gridfs(image_data, filename, photo.content_type)
            photo_ids.append(file_id)

    # Handle location field: convert dictionary to string if necessary
    if isinstance(location, dict):
        location_str = location.get("description", str(location))
    else:
        location_str = location

    report_data = {
        "type": "FOUND",
        "subject": subject_type,
        "refs": ref_ids,
        "description_text": description_text,
        "language": language,
        "photo_ids": photo_ids, # Use GridFS IDs
        "location": location_str,
        "status": "OPEN",
        "created_at": datetime.utcnow()
    }
    
    # Insert into MongoDB
    new_report = await database["reports"].insert_one(report_data)
    created_report = await database["reports"].find_one({"_id": new_report.inserted_id})

    # Start matching process in the background
    asyncio.create_task(run_matching_job(str(new_report.inserted_id), created_report, database))
    
    return ReportSchema.model_validate(created_report)


@router.get("/reports/", response_model=List[ReportSchema]) # Re-added response_model
async def list_reports(
    type: Optional[str] = Query(None, description="Filter by report type (LOST or FOUND)"), # Changed Literal to str
    status: Optional[Literal["OPEN", "MATCHED", "REUNITED", "CLOSED"]] = Query(None, description="Filter by report status"),
    database: MongoClient = Depends(get_database) # Reverted to MongoDB client dependency
):
    query = {}
    if type:
        query["type"] = type.upper() # Ensure case-insensitive matching
    if status:
        query["status"] = status.upper() # Ensure case-insensitive matching

    reports = await database["reports"].find(query).to_list(1000) # Limit to 1000 reports
    
    # For each report, convert photo_ids to base64 images for the client
    # This is a placeholder for now, actual image serving would be a separate endpoint
    for report in reports:
        report["photo_urls"] = [] # Placeholder for actual image URLs
        # In a real app, you'd have an endpoint like /images/{file_id}
        # For now, we'll just not return the actual image data in the list view

        # Ensure location is a string for existing reports
        if isinstance(report.get("location"), dict):
            report["location"] = report["location"].get("description", str(report["location"]))

    validated_reports = []
    for report in reports:
        try:
            validated_reports.append(ReportSchema.model_validate(report))
        except Exception as e:
            print(f"Validation error for report {report.get('_id')}: {e}") # Log the error
            # Optionally, you could log the entire report or specific fields for more debugging
            # print(f"Problematic report data: {report}")

    return validated_reports # Return only successfully validated reports

@router.get("/reports/{report_id}", response_model=ReportSchema)
async def get_report(report_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Invalid report ID format")
    
    report = await database["reports"].find_one({"_id": ObjectId(report_id)})
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Convert photo_ids to base64 images for the client (example, consider a dedicated image endpoint)
    # This is for fetching a single report, where returning image data might be more relevant
    report_photos_b64 = []
    for file_id in report.get("photo_ids", []):
        image_data = await get_image_from_gridfs(file_id)
        if image_data:
            report_photos_b64.append(base64.b64encode(image_data).decode("utf-8"))
    
    report["photo_urls"] = report_photos_b64 # This will contain base64 encoded images
    
    return ReportSchema.model_validate(report)

@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Invalid report ID format")
    
    # Retrieve report to get photo_ids for GridFS deletion
    report_to_delete = await database["reports"].find_one({"_id": ObjectId(report_id)})
    if not report_to_delete:
        raise HTTPException(status_code=404, detail="Report not found")

    # Delete associated images from GridFS
    fs_bucket = get_gridfs_bucket()
    for file_id_str in report_to_delete.get("photo_ids", []):
        try:
            await fs_bucket.delete(ObjectId(file_id_str))
        except Exception as e:
            print(f"Error deleting GridFS file {file_id_str}: {e}")

    delete_result = await database["reports"].delete_one({"_id": ObjectId(report_id)})
    
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"message": "Report deleted successfully"}
