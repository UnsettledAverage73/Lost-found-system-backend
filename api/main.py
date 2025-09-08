# backend/api/main.py

import uuid
import base64
import numpy as np
from datetime import datetime
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, WebSocket
from fastapi import WebSocketDisconnect # Import WebSocketDisconnect
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware

from models.schemas import (
    PersonSchema, ItemSchema, ReportSchema, 
    EmbeddingSchema, MatchSchema, UserSchema, NotificationLogEntry
)
from core.config import (
    MATCH_ACCURACY_TARGET, AVERAGE_MATCH_TIME_TARGET_MINUTES,
    REUNIFICATION_RATE_TARGET, FALSE_POSITIVE_RATE_TARGET, OFFLINE_SYNC_RELIABILITY_TARGET
)
from core.database import get_database, startup_db_client, shutdown_db_client # Re-added MongoDB imports

# Import ML functions
from ml.embeddings import get_face_embeddings, get_image_embedding, get_text_embedding, calculate_fused_score
from ml.matcher import run_matching_job, initialize_faiss_index, faiss_indexes
# from ml.speech_to_text import transcribe_audio # Temporarily disabled speech-to-text functionality
from core.websocket_manager import manager # Import the WebSocket manager

# Load environment variables
load_dotenv()

# Existing FastAPI app instance
app = FastAPI(
    title="LOFT Backend API",
    description="API for the Lost & Found System",
    version="0.1.0",
)

origins = [
    "http://localhost:3000",  # Your frontend's origin
    "http://localhost",
    "https://loft-backend.onrender.com", # Add backend's own URL for potential internal calls or testing
    "https://loft-rnk7.onrender.com" # Frontend's deployed URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "x-refresh-token"],
)

@app.on_event("startup")
async def startup():
    await startup_db_client() # Call MongoDB startup
    print("Initializing FAISS indexes...")
    faiss_indexes["face"] = initialize_faiss_index(512) # DeepFace ArcFace: 512
    faiss_indexes["image"] = initialize_faiss_index(512) # CLIP: 512
    faiss_indexes["text"] = initialize_faiss_index(384) # SBERT: 384
    print("FAISS indexes initialized.")

@app.on_event("shutdown")
async def shutdown():
    await shutdown_db_client() # Call MongoDB shutdown

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Keep the connection open, no need to receive messages from client for now
            await websocket.receive_text() # This will block until a message is received
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        print(f"WebSocket disconnected for user: {user_id}")

# --- API Endpoints ---

from .routers import reports, matches, qr, users, audio, notifications, auth
app.include_router(reports.router)
app.include_router(matches.router)
app.include_router(qr.router)
app.include_router(users.router)
app.include_router(audio.router)
app.include_router(notifications.router)
app.include_router(auth.router)
