from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict # Import ConfigDict for Pydantic V2
# from bson import ObjectId # Removed MongoDB ObjectId import

# Removed PyObjectId class as it's MongoDB specific

class PersonSchema(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    name: Optional[str] = Field(None, description="Name of the person")
    age: Optional[int] = Field(None, description="Age of the person")
    language: str = Field(..., description="Primary language of the person")
    photo_ids: List[str] = Field([], description="Supabase Storage IDs of stored photos of the person") # Changed description
    qr_id: Optional[str] = Field(None, description="QR code ID if registered")
    guardian_contact: Optional[str] = Field(None, description="Contact information for guardian")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    # Removed json_encoders and allow_population_by_field_name as they are MongoDB specific or Pydantic V1

class ItemSchema(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    type: str = Field(..., description="Type of item (e.g., 'bag', 'phone')")
    color: str = Field(..., description="Color of the item")
    brand: Optional[str] = Field(None, description="Brand of the item")
    photo_ids: List[str] = Field([], description="Supabase Storage IDs of stored photos of the item") # Changed description
    qr_id: Optional[str] = Field(None, description="QR code ID if registered")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class ReportSchema(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    type: Literal["LOST", "FOUND"] = Field(..., description="Type of report")
    subject_type: Literal["PERSON", "ITEM"] = Field(..., alias="subject", description="Subject type of the report")
    ref_ids: List[str] = Field(..., alias="refs", description="List of person_id or item_id associated with the report")
    description_text: str = Field(..., alias="desc_text", description="Description text of the lost/found item/person")
    language: str = Field(..., alias="lang", description="Language of the description")
    photo_ids: List[str] = Field([], description="Supabase Storage IDs of stored photos for the report") # Changed description
    location: str = Field(..., description="Location where the person/item was lost/found")
    status: Literal["OPEN", "MATCHED", "REUNITED", "CLOSED"] = Field("OPEN", description="Status of the report")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of report creation")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class EmbeddingSchema(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    report_id: str = Field(..., description="ID of the associated report")
    face_vecs: List[List[float]] = Field([], description="List of face embedding vectors")
    image_vec: Optional[List[float]] = Field(None, description="CLIP image embedding vector")
    text_vec: Optional[List[float]] = Field(None, description="Sentence-transformer text embedding vector")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of embedding creation")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class MatchSchema(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    lost_report_id: str = Field(..., description="ID of the lost report")
    found_report_id: str = Field(..., description="ID of the found report")
    scores: dict = Field(..., description="Dictionary of individual modality scores (face, image, text)")
    fused_score: float = Field(..., description="Weighted average of modality scores")
    status: Literal["PENDING", "CONFIRMED_REUNITED", "FALSE_MATCH"] = Field("PENDING", description="Status of the match")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of match creation")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class UserSchema(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    role: Literal["VOLUNTEER", "ADMIN"] = Field(..., description="Role of the user")
    contact: str = Field(..., description="Phone number or email for mock alerts")
    consent_face_qr: bool = Field(False, description="User consent for facial recognition and QR tagging")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class UserRegisterSchema(BaseModel):
    contact: str = Field(..., description="Phone number or email for user account")
    password: str = Field(..., description="User's password")
    role: Literal["VOLUNTEER", "ADMIN"] = Field("VOLUNTEER", description="Role of the user, defaults to VOLUNTEER")
    consent_face_qr: bool = Field(False, description="User consent for facial recognition and QR tagging")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

class NotificationLogEntry(BaseModel):
    # id: Optional[PyObjectId] = Field(alias="_id") # Removed MongoDB-specific ID
    id: Optional[str] = Field(None, alias="_id") # Using str for Supabase IDs
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    match_id: Optional[str] = None
    report_id: Optional[str] = None
    recipient: str
    message: str
    type: Literal["SMS", "CALL"]
    status: Literal["SIMULATED_SENT", "FAILED"] = "SIMULATED_SENT"

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
