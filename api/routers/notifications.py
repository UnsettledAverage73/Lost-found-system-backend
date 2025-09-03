from fastapi import APIRouter, HTTPException, Depends, Form, status
from typing import Optional, Literal
from datetime import datetime
# from pymongo import MongoClient # Removed MongoDB client import
# from bson import ObjectId # Removed MongoDB ObjectId import

from backend.models.schemas import NotificationLogEntry # Removed PyObjectId
# from backend.core.database import get_database # Removed MongoDB database import
from backend.core.supabase import get_supabase_client
from supabase import Client # Import Client for type hinting

router = APIRouter()

@router.post("/notifications/send_mock", response_model=NotificationLogEntry)
async def send_mock_notification(
    match_id: Optional[str] = Form(None),
    report_id: Optional[str] = Form(None),
    recipient: str = Form(...),
    message: str = Form(...),
    notification_type: Literal["SMS", "CALL"] = Form(..., alias="type"),
    supabase: Client = Depends(get_supabase_client) # Use Supabase client dependency
):
    """
    Simulates sending a notification (SMS/Call) and logs the attempt to Supabase.
    """
    notification_entry_data = {
        "match_id": match_id,
        "report_id": report_id,
        "recipient": recipient,
        "message": message,
        "type": notification_type,
        "status": "SIMULATED_SENT",
        "timestamp": datetime.utcnow().isoformat() # Store as ISO format string
    }
    
    response = supabase.from_("notification_logs").insert([notification_entry_data]).execute()

    if response.data and len(response.data) > 0:
        created_log_entry = response.data[0]
        notification_entry = NotificationLogEntry(**created_log_entry)
        print(f"Simulated {notification_type} notification sent to {recipient}: {message}")
        print(f"Notification Log ID: {notification_entry.id}")
        return notification_entry
    else:
        print(f"Supabase insert failed for notification log: {response.last_error}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to log notification")
