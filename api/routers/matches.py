from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Literal
import base64

from backend.models.schemas import MatchSchema, ReportSchema # Removed PyObjectId
# from backend.core.database import get_database, get_image_from_gridfs # Removed MongoDB imports
from backend.ml.matcher import run_matching_job
# from pymongo import MongoClient # Removed MongoDB client import
# from bson import ObjectId # Removed MongoDB ObjectId import

from backend.core.supabase import get_supabase_client, get_file_from_supabase_storage
from supabase import Client # Import Client for type hinting
from backend.api.routers.reports import SUPABASE_REPORT_PHOTOS_BUCKET # Import bucket name

router = APIRouter()

@router.post("/match/run")
async def run_match(report_id: str, supabase: Client = Depends(get_supabase_client)):
    # Fetch report data from Supabase
    response = supabase.from_("reports").select("*").eq("id", report_id).single().execute()
    report_data = response.data

    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Prepare data for matching job
    report_with_b64_images = ReportSchema(**report_data).dict()
    report_with_b64_images["photo_urls"] = []
    for url in report_data.get("photo_urls", []):
        # Extract file path from URL for Supabase Storage retrieval
        path_segments = url.split("/")
        bucket_idx = path_segments.index(SUPABASE_REPORT_PHOTOS_BUCKET)
        file_path_in_storage = "/".join(path_segments[bucket_idx+1:])

        img_bytes = await get_file_from_supabase_storage(SUPABASE_REPORT_PHOTOS_BUCKET, file_path_in_storage)
        if img_bytes:
            report_with_b64_images["photo_urls"].append(base64.b64encode(img_bytes).decode("utf-8"))

    await run_matching_job(report_id, report_with_b64_images, supabase)
    return {"message": f"Matching process initiated for report {report_id}"}

@router.get("/matches", response_model=List[MatchSchema])
async def list_matches(
    status_filter: Optional[Literal["PENDING", "CONFIRMED_REUNITED", "FALSE_MATCH"]] = Depends(),
    supabase: Client = Depends(get_supabase_client)
):
    query = supabase.from_("matches").select("*")
    
    if status_filter:
        query = query.eq("status", status_filter)
    
    response = await query.execute()
    if response.data:
        return [MatchSchema(**match) for match in response.data]
    else:
        return []

@router.post("/matches/{match_id}/confirm")
async def confirm_match(match_id: str, supabase: Client = Depends(get_supabase_client)):
    # Update match status in Supabase
    response = supabase.from_("matches").update({"status": "CONFIRMED_REUNITED"}).eq("id", match_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Match not found or update failed")
    
    # Fetch the updated match to get report IDs
    match_data_response = supabase.from_("matches").select("lost_report_id, found_report_id").eq("id", match_id).single().execute()
    match_data = match_data_response.data

    if not match_data:
        raise HTTPException(status_code=404, detail="Match data not found after update")

    lost_report_id = match_data["lost_report_id"]
    found_report_id = match_data["found_report_id"]

    # Update associated reports in Supabase
    supabase.from_("reports").update({"status": "REUNITED"}).eq("id", lost_report_id).execute()
    supabase.from_("reports").update({"status": "REUNITED"}).eq("id", found_report_id).execute()

    return {"message": f"Match {match_id} confirmed as reunited."}

@router.post("/matches/{match_id}/flag_false")
async def flag_false_match(match_id: str, supabase: Client = Depends(get_supabase_client)):
    response = supabase.from_("matches").update({"status": "FALSE_MATCH"}).eq("id", match_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Match not found or update failed")

    print(f"Match {match_id} flagged as false.")
    return {"message": f"Match {match_id} flagged as false."}
