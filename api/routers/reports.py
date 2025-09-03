from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status, Query
from typing import List, Optional, Literal
import base64
import uuid # Import uuid for generating unique file names

from backend.models.schemas import ReportSchema, PersonSchema, ItemSchema # Removed PyObjectId
# from backend.core.database import get_database, store_image_in_gridfs, get_image_from_gridfs # Removed MongoDB database and GridFS imports
from backend.ml.matcher import run_matching_job
from backend.ml.speech_to_text import transcribe_audio
# from pymongo import MongoClient # Removed MongoDB client import
# from bson import ObjectId # Removed MongoDB ObjectId import

from backend.core.supabase import get_supabase_client, upload_file_to_supabase_storage, get_file_from_supabase_storage
from supabase import Client # Import Client for type hinting

router = APIRouter()

SUPABASE_REPORT_PHOTOS_BUCKET = "report_photos" # Define the Supabase bucket for report photos

@router.post("/reports/lost", response_model=ReportSchema)
async def create_lost_report(
    subject_type: Literal["PERSON", "ITEM"] = Form(..., alias="subject"),
    ref_ids_str: str = Form(..., alias="refs", description="Comma-separated IDs of person/item"),
    description_text: str = Form(..., alias="desc_text"),
    language: str = Form(..., alias="lang"),
    location: str = Form(...),
    photos: Optional[List[UploadFile]] = File(None),
    supabase: Client = Depends(get_supabase_client) # Use Supabase client dependency
):
    photo_urls = [] # Store public URLs from Supabase Storage
    if photos:
        for photo in photos:
            file_contents = await photo.read()
            file_extension = photo.filename.split(".")[-1] if "." in photo.filename else "jpg"
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path_in_storage = f"lost_reports/{unique_filename}"
            
            public_url = await upload_file_to_supabase_storage(
                SUPABASE_REPORT_PHOTOS_BUCKET, 
                file_path_in_storage, 
                file_contents, 
                photo.content_type
            )
            photo_urls.append(public_url)

    ref_ids = [r_id.strip() for r_id in ref_ids_str.split(',')]

    new_report_data = {
        "type": "LOST",
        "subject_type": subject_type,
        "ref_ids": ref_ids,
        "description_text": description_text,
        "language": language,
        "photo_urls": photo_urls, # Store URLs instead of GridFS IDs
        "location": location,
        "status": "OPEN"
    }
    
    # Insert into Supabase
    response = supabase.from_("reports").insert(new_report_data).execute()
    if response.data and len(response.data) > 0:
        created_report = response.data[0]
        new_report = ReportSchema(**created_report)
        print(f"Created LOST report: {new_report.id}")

        # Prepare data for matching job: need actual base64 image strings
        report_with_b64_images = new_report.dict()
        report_with_b64_images["photo_urls"] = [] # Renaming this key for consistency with ml/matcher.py expected input
        for url in new_report.photo_urls:
            # Extract file path from URL for Supabase Storage retrieval
            # Assuming URL format: {SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_path_in_storage}
            path_segments = url.split("/")
            bucket_idx = path_segments.index(SUPABASE_REPORT_PHOTOS_BUCKET)
            file_path_in_storage = "/".join(path_segments[bucket_idx+1:])

            img_bytes = await get_file_from_supabase_storage(SUPABASE_REPORT_PHOTOS_BUCKET, file_path_in_storage)
            if img_bytes:
                report_with_b64_images["photo_urls"].append(base64.b64encode(img_bytes).decode("utf-8"))

        # Asynchronously trigger matching job
        await run_matching_job(str(new_report.id), report_with_b64_images, supabase) # Pass supabase client
        return new_report
    else:
        print(f"Supabase insert failed: {response.last_error}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create report")

@router.post("/reports/found", response_model=ReportSchema)
async def create_found_report(
    subject_type: Literal["PERSON", "ITEM"] = Form(..., alias="subject"),
    ref_ids_str: str = Form(..., alias="refs", description="Comma-separated IDs of person/item"),
    description_text: Optional[str] = Form(None, alias="desc_text"),
    audio_file: Optional[UploadFile] = File(None),
    language: str = Form(..., alias="lang"),
    location: str = Form(...),
    photos: List[UploadFile] = File([]),
    supabase: Client = Depends(get_supabase_client) # Use Supabase client dependency
):
    photo_urls = [] # Store public URLs from Supabase Storage
    for photo in photos:
        file_contents = await photo.read()
        file_extension = photo.filename.split(".")[-1] if "." in photo.filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path_in_storage = f"found_reports/{unique_filename}"

        public_url = await upload_file_to_supabase_storage(
            SUPABASE_REPORT_PHOTOS_BUCKET,
            file_path_in_storage,
            file_contents,
            photo.content_type
        )
        photo_urls.append(public_url)

    transcribed_text = None
    if audio_file:
        audio_contents = await audio_file.read()
        transcribed_text = transcribe_audio(audio_contents)

        if transcribed_text:
            if description_text:
                description_text = transcribed_text + " " + description_text
            else:
                description_text = transcribed_text
            print(f"Transcribed audio: {transcribed_text}")
        else:
            print("Audio transcription failed.")

    if not description_text:
        raise HTTPException(status_code=400, detail="Description text or audio file is required.")

    ref_ids = [r_id.strip() for r_id in ref_ids_str.split(',')]

    new_report_data = {
        "type": "FOUND",
        "subject_type": subject_type,
        "ref_ids": ref_ids,
        "description_text": description_text,
        "language": language,
        "photo_urls": photo_urls, # Store URLs instead of GridFS IDs
        "location": location,
        "status": "OPEN"
    }
    
    # Insert into Supabase
    response = supabase.from_("reports").insert(new_report_data).execute()
    if response.data and len(response.data) > 0:
        created_report = response.data[0]
        new_report = ReportSchema(**created_report)
        print(f"Created FOUND report: {new_report.id}")

        # Prepare data for matching job
        report_with_b64_images = new_report.dict()
        report_with_b64_images["photo_urls"] = []
        for url in new_report.photo_urls:
            # Extract file path from URL for Supabase Storage retrieval
            path_segments = url.split("/")
            bucket_idx = path_segments.index(SUPABASE_REPORT_PHOTOS_BUCKET)
            file_path_in_storage = "/".join(path_segments[bucket_idx+1:])

            img_bytes = await get_file_from_supabase_storage(SUPABASE_REPORT_PHOTOS_BUCKET, file_path_in_storage)
            if img_bytes:
                report_with_b64_images["photo_urls"].append(base64.b64encode(img_bytes).decode("utf-8"))

        await run_matching_job(str(new_report.id), report_with_b64_images, supabase) # Pass supabase client
        return new_report
    else:
        print(f"Supabase insert failed: {response.last_error}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create report")

@router.get("/reports", response_model=List[ReportSchema])
async def list_reports(
    type: Optional[Literal["LOST", "FOUND"]] = None,
    status_filter: Optional[Literal["OPEN", "MATCHED", "REUNITED", "CLOSED"]] = Query(None, alias="status"),
    supabase: Client = Depends(get_supabase_client)
):
    query = supabase.from_("reports").select("*")
    
    if type:
        query = query.eq("type", type)
    if status_filter:
        query = query.eq("status", status_filter)
    
    response = await query.execute()
    if response.data:
        return [ReportSchema(**report) for report in response.data]
    else:
        print(f"Supabase select failed: {response.last_error}")
        return []
