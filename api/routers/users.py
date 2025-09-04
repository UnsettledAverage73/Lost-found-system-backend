from fastapi import APIRouter, HTTPException, Depends, Form, status
from typing import Optional, Literal
from datetime import datetime
from pymongo import MongoClient # Re-added MongoDB client import
from bson import ObjectId # Re-added MongoDB ObjectId import

from models.schemas import NotificationLogEntry, PyObjectId # Re-added PyObjectId
from core.database import get_database # Re-added MongoDB database import
# from backend.core.supabase import get_supabase_client # Removed Supabase imports
# from supabase import Client # Removed Client for type hinting

router = APIRouter()

@router.post("/notifications/send_mock", response_model=NotificationLogEntry)
async def send_mock_notification(
    match_id: Optional[str] = Form(None),
    report_id: Optional[str] = Form(None),
    recipient: str = Form(...),
    message: str = Form(...),
    notification_type: Literal["SMS", "CALL"] = Form(..., alias="type"),
    database: MongoClient = Depends(get_database) # Reverted to MongoDB client dependency
):
    """
    Simulates sending a notification (SMS/Call) and logs the attempt to MongoDB.
    """
    notification_entry_data = {
        "timestamp": datetime.utcnow(),
        "match_id": ObjectId(match_id) if match_id and ObjectId.is_valid(match_id) else None,
        "report_id": ObjectId(report_id) if report_id and ObjectId.is_valid(report_id) else None,
        "recipient": recipient,
        "message": message,
        "type": notification_type,
        "status": "SIMULATED_SENT"
    }
    
    insert_result = await database["notification_logs"].insert_one(notification_entry_data)
    
    if insert_result.inserted_id:
        created_log_entry = await database["notification_logs"].find_one({"_id": insert_result.inserted_id})
        notification_entry = NotificationLogEntry.model_validate(created_log_entry)
        print(f"Simulated {notification_type} notification sent to {recipient}: {message}")
        print(f"Notification Log ID: {notification_entry.id}")
        return notification_entry
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to log notification")
