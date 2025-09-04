# backend/models/schemas.py

from datetime import datetime
from typing import List, Optional, Literal, Any

from pydantic import BaseModel, Field
from bson import ObjectId # Re-added MongoDB ObjectId import

# Custom PyObjectId class for MongoDB ObjectIds
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info: Any):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    # Corrected for Pydantic V2: Use __get_pydantic_json_schema__
    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        json_schema = handler(schema)
        json_schema.update(type="string")
        return json_schema

class PersonSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    name: Optional[str] = Field(None, description="Name of the person")
    age: Optional[int] = Field(None, description="Age of the person")
    language: str = Field(..., description="Primary language of the person")
    photo_ids: List[str] = Field([], description="GridFS IDs of stored photos of the person") # Changed description
    qr_id: Optional[str] = Field(None, description="QR code ID if registered")
    guardian_contact: Optional[str] = Field(None, description="Contact information for guardian")

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ItemSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    type: str = Field(..., description="Type of item (e.g., 'bag', 'phone')")
    color: str = Field(..., description="Color of the item")
    brand: Optional[str] = Field(None, description="Brand of the item")
    photo_ids: List[str] = Field([], description="GridFS IDs of stored photos of the item") # Changed description
    qr_id: Optional[str] = Field(None, description="QR code ID if registered")

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ReportSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    type: Literal["LOST", "FOUND"] = Field(..., description="Type of report")
    subject_type: Literal["PERSON", "ITEM"] = Field(..., alias="subject", description="Subject type of the report")
    ref_ids: List[str] = Field(..., alias="refs", description="List of person_id or item_id associated with the report")
    description_text: str = Field(..., alias="desc_text", description="Description text of the lost/found item/person")
    language: str = Field(..., description="Language of the description") # Changed: Removed alias="lang"
    photo_ids: List[str] = Field([], description="GridFS IDs of stored photos for the report") # Changed description
    location: str = Field(..., description="Location where the person/item was lost/found")
    status: Literal["OPEN", "MATCHED", "REUNITED", "CLOSED"] = Field("OPEN", description="Status of the report")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of report creation")

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class EmbeddingSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    report_id: str = Field(..., description="ID of the associated report")
    face_vecs: List[List[float]] = Field([], description="List of face embedding vectors")
    image_vec: Optional[List[float]] = Field(None, description="CLIP image embedding vector")
    text_vec: Optional[List[float]] = Field(None, description="Sentence-transformer text embedding vector")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of embedding creation")

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class MatchSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    lost_report_id: str = Field(..., description="ID of the lost report")
    found_report_id: str = Field(..., description="ID of the found report")
    scores: dict = Field(..., description="Dictionary of individual modality scores (face, image, text)")
    fused_score: float = Field(..., description="Weighted average of modality scores")
    status: Literal["PENDING", "CONFIRMED_REUNITED", "FALSE_MATCH"] = Field("PENDING", description="Status of the match")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of match creation")

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class UserSchema(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    role: Literal["VOLUNTEER", "ADMIN"] = Field(..., description="Role of the user")
    contact: str = Field(..., description="Phone number or email for mock alerts")
    consent_face_qr: bool = Field(False, description="User consent for facial recognition and QR tagging")

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class UserRegisterSchema(BaseModel):
    contact: str = Field(..., description="Phone number or email for user account")
    password: str = Field(..., description="User's password")
    role: Literal["VOLUNTEER", "ADMIN"] = Field("VOLUNTEER", description="Role of the user, defaults to VOLUNTEER")
    consent_face_qr: bool = Field(False, description="User consent for facial recognition and QR tagging")

    # Using Pydantic V1 Config style for consistency, though not strictly needed here
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class NotificationLogEntry(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id") # Reverted to MongoDB-specific ID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    match_id: Optional[str] = None
    report_id: Optional[str] = None
    recipient: str
    message: str
    type: Literal["SMS", "CALL"]
    status: Literal["SIMULATED_SENT", "FAILED"] = "SIMULATED_SENT"

    # Reverted to Pydantic V1 Config for ObjectId serialization
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
