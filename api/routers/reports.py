from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status, Query
from typing import List, Optional, Literal
import base64
import uuid # Import uuid for generating unique file names
from datetime import datetime # Added datetime import
from fastapi.responses import Response # Import Response for serving images
import asyncio # Import asyncio for create_task

from models.schemas import ReportSchema, PersonSchema, ItemSchema, PyObjectId # Re-added PyObjectId
from core.database import get_database, store_image_in_gridfs, get_image_from_gridfs # Re-added MongoDB database and GridFS imports
from ml.matcher import run_matching_job
# from ml.speech_to_text import transcribe_audio # Temporarily disabled speech-to-text functionality
from pymongo import MongoClient # Re-added MongoDB client import
from bson import ObjectId # Re-added MongoDB ObjectId import
from gridfs import GridFSBucket # Added GridFSBucket import
from core.security import get_current_user # Import to get current user
from models.schemas import UserSchema # Import UserSchema for type hinting

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
    latitude: float = Form(..., description="Latitude of the location"),
    longitude: float = Form(..., description="Longitude of the location"),
    location_description: Optional[str] = Form(None, alias="location_desc", description="Human-readable description of the location"),
    photos: Optional[List[UploadFile]] = File(None), # Made photos optional
    database: MongoClient = Depends(get_database), # Reverted to MongoDB client dependency
    current_user: UserSchema = Depends(get_current_user), # Inject current user
    # Person-specific details
    is_child: Optional[bool] = Form(None, description="Indicates if the person is a child"),
    height_cm: Optional[float] = Form(None, description="Height in centimeters"),
    weight_kg: Optional[float] = Form(None, description="Weight in kilograms"),
    identifying_features: Optional[str] = Form(None, description="Distinctive features"),
    clothing_description: Optional[str] = Form(None, description="Description of clothing"),
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

    report_data = {
        "type": "LOST",
        "subject": subject_type,
        "refs": ref_ids,
        "description_text": description_text,
        "language": language,
        "photo_ids": photo_ids, # Use GridFS IDs
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "description": location_description,
        },
        "status": "OPEN",
        "created_at": datetime.utcnow(),
        "posted_by_contact": current_user.contact # Add posted_by_contact
    }
    
    if subject_type == "PERSON":
        report_data["person_details"] = PersonSchema(
            name=None, # Name can be derived from ref_ids or handled separately if needed
            age=None,  # Age can be derived or handled separately if needed
            language=language, # Use report's language
            photo_ids=photo_ids, # Use report's photo_ids
            is_child=is_child,
            height_cm=height_cm,
            weight_kg=weight_kg,
            identifying_features=identifying_features,
            clothing_description=clothing_description,
            guardian_contact=None # Can be added if passed directly to person_details
        ).model_dump(exclude_unset=True) # Use model_dump to exclude unset fields
    
    # Insert into MongoDB
    new_report = await database["reports"].insert_one(report_data)
    created_report = await database["reports"].find_one({"_id": new_report.inserted_id})
    
    # Start matching process in the background
    asyncio.create_task(run_matching_job(str(new_report.inserted_id), created_report, database))
    
    # Generate photo URLs for the created report
    created_report["photo_urls"] = [f"/reports/images/{str(file_id)}" for file_id in photo_ids]
    
    return ReportSchema.model_validate(created_report)


@router.post("/reports/found", response_model=ReportSchema)
async def create_found_report(
    subject_type: Literal["PERSON", "ITEM"] = Form(..., alias="subject"),
    ref_ids_str: str = Form(..., alias="refs", description="Comma-separated IDs of person/item"),
    description_text: str = Form(..., alias="desc_text"),
    language: str = Form(..., alias="lang"),
    latitude: float = Form(..., description="Latitude of the location"),
    longitude: float = Form(..., description="Longitude of the location"),
    location_description: Optional[str] = Form(None, alias="location_desc", description="Human-readable description of the location"),
    photos: Optional[List[UploadFile]] = File(None), # Made photos optional
    database: MongoClient = Depends(get_database), # Reverted to MongoDB client dependency
    current_user: UserSchema = Depends(get_current_user), # Inject current user
    # Person-specific details
    is_child: Optional[bool] = Form(None, description="Indicates if the person is a child"),
    height_cm: Optional[float] = Form(None, description="Height in centimeters"),
    weight_kg: Optional[float] = Form(None, description="Weight in kilograms"),
    identifying_features: Optional[str] = Form(None, description="Distinctive features"),
    clothing_description: Optional[str] = Form(None, description="Description of clothing"),
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

    report_data = {
        "type": "FOUND",
        "subject": subject_type,
        "refs": ref_ids,
        "description_text": description_text,
        "language": language,
        "photo_ids": photo_ids, # Use GridFS IDs
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "description": location_description,
        },
        "status": "OPEN",
        "created_at": datetime.utcnow(),
        "posted_by_contact": current_user.contact # Add posted_by_contact
    }
    
    if subject_type == "PERSON":
        report_data["person_details"] = PersonSchema(
            name=None, # Name can be derived from ref_ids or handled separately if needed
            age=None,  # Age can be derived or handled separately if needed
            language=language, # Use report's language
            photo_ids=photo_ids, # Use report's photo_ids
            is_child=is_child,
            height_cm=height_cm,
            weight_kg=weight_kg,
            identifying_features=identifying_features,
            clothing_description=clothing_description,
            guardian_contact=None # Can be added if passed directly to person_details
        ).model_dump(exclude_unset=True) # Use model_dump to exclude unset fields
    
    # Insert into MongoDB
    new_report = await database["reports"].insert_one(report_data)
    created_report = await database["reports"].find_one({"_id": new_report.inserted_id})

    # Start matching process in the background
    asyncio.create_task(run_matching_job(str(new_report.inserted_id), created_report, database))
    
    # Generate photo URLs for the created report
    created_report["photo_urls"] = [f"/reports/images/{str(file_id)}" for file_id in photo_ids]
    
    return ReportSchema.model_validate(created_report)


@router.get("/reports/", response_model=List[ReportSchema])
async def list_reports(
    type: Optional[str] = Query(None, description="Filter by report type (LOST or FOUND)"), # Changed Literal to str
    status: Optional[Literal["OPEN", "MATCHED", "REUNITED", "CLOSED"]] = Query(None, description="Filter by report status"),
    skip: int = Query(0, description="Number of items to skip"),
    limit: int = Query(10, description="Maximum number of items to return"),
    database: MongoClient = Depends(get_database), # Reverted to MongoDB client dependency
    current_user: UserSchema = Depends(get_current_user) # Ensure user is authenticated
):
    query = {}
    if type:
        query["type"] = type.upper() # Ensure case-insensitive matching
    if status:
        query["status"] = status.upper() # Ensure case-insensitive matching

    reports_cursor = database["reports"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    reports = await reports_cursor.to_list(length=limit)
    
    # For each report, convert photo_ids to base64 images for the client
    # This is a placeholder for now, actual image serving would be a separate endpoint
    for report in reports:
        report["photo_urls"] = [f"/reports/images/{str(file_id)}" for file_id in report.get("photo_ids", [])]

    return [ReportSchema.model_validate(report) for report in reports]

@router.get("/reports/{report_id}", response_model=ReportSchema)
async def get_report(report_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Invalid report ID format")
    
    report = await database["reports"].find_one({"_id": ObjectId(report_id)})
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Generate photo URLs for the report
    report["photo_urls"] = [f"/reports/images/{str(file_id)}" for file_id in report.get("photo_ids", [])]
    
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

@router.get("/reports/images/{file_id}")
async def get_report_image(file_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    image_data = await get_image_from_gridfs(ObjectId(file_id))
    if image_data is None:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Determine content type (you might store this in GridFS metadata when uploading)
    # For now, let's assume it's a JPEG or PNG for simplicity.
    # A more robust solution would store content_type in GridFS metadata.
    # We'll fetch file metadata from GridFS to get the content type.
    fs_bucket = GridFSBucket(database.client.get_database(database.name))
    grid_out = await fs_bucket.open_download_stream(ObjectId(file_id))
    content_type = grid_out.content_type if grid_out.content_type else "application/octet-stream"
    
    return Response(content=image_data, media_type=content_type)
