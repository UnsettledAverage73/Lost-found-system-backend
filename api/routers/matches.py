from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Literal
import base64
import asyncio # Import asyncio for background tasks

from models.schemas import MatchSchema, ReportSchema, PyObjectId # Re-added PyObjectId
from core.database import get_database, get_image_from_gridfs # Re-added MongoDB imports
from ml.matcher import run_matching_job
from pymongo import MongoClient # Re-added MongoDB client import
from bson import ObjectId # Re-added MongoDB ObjectId import

# from core.supabase import get_supabase_client, get_file_from_supabase_storage # Removed Supabase imports
# from supabase import Client # Removed Client for type hinting
# from .reports import SUPABASE_REPORT_PHOTOS_BUCKET # Removed Supabase bucket name

router = APIRouter()

@router.post("/match/run/{report_id}") # Changed to path parameter
async def run_match(report_id: str, database: MongoClient = Depends(get_database)): # Reverted to MongoDB client
    if not ObjectId.is_valid(report_id):
        raise HTTPException(status_code=400, detail="Invalid report ID format")
    
    # Fetch report data from MongoDB
    report_data = await database["reports"].find_one({"_id": ObjectId(report_id)})

    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Prepare data for matching job, converting GridFS IDs to base64 images
    report_with_b64_images = ReportSchema.model_validate(report_data).model_dump()
    report_with_b64_images["photo_urls"] = [] # Placeholder for base64 images
    for file_id in report_data.get("photo_ids", []):
        img_bytes = await get_image_from_gridfs(file_id)
        if img_bytes:
            report_with_b64_images["photo_urls"].append(base64.b64encode(img_bytes).decode("utf-8"))

    # Run matching job in the background
    asyncio.create_task(run_matching_job(report_id, report_with_b64_images, database)) # Pass database client
    return {"message": f"Matching process initiated for report {report_id}"}


@router.get("/matches", response_model=List[MatchSchema])
async def list_matches(
    status_filter: Optional[Literal["PENDING", "CONFIRMED_REUNITED", "FALSE_MATCH"]] = Query(None), # Changed Depends() to Query(None)
    database: MongoClient = Depends(get_database) # Reverted to MongoDB client dependency
):
    query = {}
    if status_filter:
        query["status"] = status_filter
    
    matches = await database["matches"].find(query).to_list(1000)
    return [MatchSchema.model_validate(match) for match in matches]

@router.post("/matches/{match_id}/confirm", response_model=MatchSchema)
async def confirm_match(match_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(match_id):
        raise HTTPException(status_code=400, detail="Invalid match ID format")

    update_result = await database["matches"].update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {"status": "CONFIRMED_REUNITED"}}
    )
    if update_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Match not found or not updated")
    
    updated_match = await database["matches"].find_one({"_id": ObjectId(match_id)})
    return MatchSchema.model_validate(updated_match)

@router.post("/matches/{match_id}/flag-false", response_model=MatchSchema)
async def flag_false_match(match_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(match_id):
        raise HTTPException(status_code=400, detail="Invalid match ID format")

    update_result = await database["matches"].update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {"status": "FALSE_MATCH"}}
    )
    if update_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Match not found or not updated")
    
    updated_match = await database["matches"].find_one({"_id": ObjectId(match_id)})
    return MatchSchema.model_validate(updated_match)

@router.get("/matches/{match_id}", response_model=MatchSchema)
async def get_match_by_id(match_id: str, database: MongoClient = Depends(get_database)):
    if not ObjectId.is_valid(match_id):
        raise HTTPException(status_code=400, detail="Invalid match ID format")

    match = await database["matches"].find_one({"_id": ObjectId(match_id)})
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchSchema.model_validate(match)
