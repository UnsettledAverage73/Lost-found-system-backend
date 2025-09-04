# ml/matcher.py

import faiss
import numpy as np
from typing import List, Dict, Optional
import os
from sklearn.metrics.pairwise import cosine_similarity
import uuid
from datetime import datetime

from models.schemas import ReportSchema, MatchSchema, ItemSchema
# from core.database import get_database # Removed MongoDB database import
from ml.embeddings import get_face_embeddings, get_image_embedding, get_text_embedding, calculate_fused_score
# from ml.speech_to_text import transcribe_audio # Removed due to temporary disable
from core.websocket_manager import manager
from core.supabase import Client # Import Client for type hinting

# Directory for FAISS indexes
FAISS_INDEX_DIR = "ml/indexes"
os.makedirs(FAISS_INDEX_DIR, exist_ok=True)

# Placeholder for loaded FAISS indexes
# In a real application, these would be loaded once at startup or managed more robustly.
faiss_indexes: Dict[str, any] = {}

# Thresholds (will be tuned later as per the plan)
PERSON_MATCH_THRESHOLD = 0.70 # Example threshold for persons
ITEM_MATCH_THRESHOLD = 0.60 # Example threshold for items

def initialize_faiss_index(dimension: int, index_type: str = "Flat") -> faiss.Index:
    """
    Initializes a FAISS index.
    'Flat' is simple brute force, good for starting. For larger datasets, explore 'IVF'.
    """
    if index_type == "Flat":
        return faiss.IndexFlatIP(dimension) # IP for inner product (cosine similarity is related)
    else:
        raise ValueError(f"Unsupported FAISS index type: {index_type}")

def load_or_create_faiss_index(modality: str, dimension: int) -> faiss.Index:
    """
    Loads an existing FAISS index or creates a new one if it doesn't exist.
    """
    index_path = os.path.join(FAISS_INDEX_DIR, f"{modality}_index.faiss")
    if os.path.exists(index_path):
        print(f"Loading existing FAISS index for {modality} from {index_path}")
        return faiss.read_index(index_path)
    else:
        print(f"Creating new FAISS index for {modality} with dimension {dimension}")
        new_index = initialize_faiss_index(dimension)
        faiss_indexes[modality] = new_index # Store reference to the newly created index
        return new_index

def update_faiss_index(modality: str, new_embeddings: np.ndarray, report_ids: List[str]):
    """
    Adds new embeddings and their corresponding report IDs to the FAISS index.
    Assumes `faiss_indexes` is globally accessible or passed around.
    Note: FAISS IndexFlatIP does not store IDs directly. We need a mapping.
    For this prototype, we'll keep a simple in-memory mapping.
    In production, this mapping would be persistent (e.g., in MongoDB).
    """
    index = faiss_indexes.get(modality)
    if index is None:
        # Determine dimension from embeddings, or set a default/expected dimension
        dimension = new_embeddings.shape[1] if new_embeddings.size > 0 else 512 # Default to 512 if no embeddings to infer
        index = load_or_create_faiss_index(modality, dimension)
        faiss_indexes[modality] = index # Ensure the global/module-level reference is updated

    # FAISS requires float32
    new_embeddings = new_embeddings.astype('float32')

    # Add vectors to the index
    index.add(new_embeddings)

    # For now, we'll simulate an ID mapping. In a real system, this would be persisted.
    if not hasattr(index, 'id_map'):
        index.id_map = [] # Initialize if not present
    index.id_map.extend(report_ids)

    # Save the updated index
    index_path = os.path.join(FAISS_INDEX_DIR, f"{modality}_index.faiss")
    faiss.write_index(index, index_path)
    print(f"Updated and saved FAISS index for {modality} with {len(new_embeddings)} new embeddings. Total vectors: {index.ntotal}")

def search_faiss_index(modality: str, query_embedding: np.ndarray, k: int = 5) -> (np.ndarray, List[str]):
    """
    Searches a FAISS index for the nearest neighbors.
    Returns scores and corresponding report IDs.
    """
    index = faiss_indexes.get(modality)
    if index is None:
        raise ValueError(f"FAISS index for modality '{modality}' not found.")

    # FAISS requires float32
    query_embedding = query_embedding.astype('float32')

    # Search for k nearest neighbors
    distances, indices = index.search(query_embedding, k)

    # Get report IDs from the index's ID map
    report_ids = [index.id_map[i] for i in indices[0]]

    return distances, report_ids

async def run_matching_job(report_id: str, report_data: dict, supabase: Client): # Changed mock_db to supabase client
    """
    Main matching job function.
    1. Extracts embeddings for a new LOST or FOUND report.
    2. Searches existing FAISS indexes.
    3. Calculates fused scores and persists top-k candidates to `matches` in Supabase.
    """
    print(f"Running matching job for report: {report_id}")

    report_type = report_data["type"] # LOST or FOUND
    subject_type = report_data["subject_type"] # PERSON or ITEM (using subject_type to align with Pydantic model)
    description_text = report_data["description_text"]
    photo_urls = report_data["photo_urls"] # These are now base64 strings passed from main.py
    
    # --- 1. Extract Embeddings ---
    face_embeddings = []
    image_embedding = None
    text_embedding = None

    if subject_type == "PERSON":
        face_embeddings = get_face_embeddings(photo_urls) # Use the base64 strings directly
        if face_embeddings:
            print(f"Generated {len(face_embeddings)} face embeddings.")
    
    # Always try to get image embedding for general visual features if photos exist
    if photo_urls:
        # For simplicity, use the first photo for image embedding if multiple exist
        image_embedding = get_image_embedding(photo_urls[0])
        if image_embedding is not None:
            print("Generated CLIP image embedding.")
        
    if description_text:
        text_embedding = get_text_embedding(description_text, report_data.get("language", "en"))
        if text_embedding is not None:
            print("Generated SBERT text embedding.")

    # Convert to numpy arrays for FAISS
    face_embeddings_np = np.array(face_embeddings).astype('float32') if face_embeddings else np.array([])
    image_embedding_np = np.array(image_embedding).astype('float32') if image_embedding is not None else np.array([])
    text_embedding_np = np.array(text_embedding).astype('float32') if text_embedding is not None else np.array([])

    # Update FAISS indexes with the new report's embeddings
    if face_embeddings_np.size > 0:
        # Before adding, check if this report_id already has embeddings in the index.
        # For simplicity, we assume new reports mean new embeddings. In a real system,
        # you'd manage updates/deletes from the FAISS index.
        update_faiss_index("face", face_embeddings_np, [report_id] * len(face_embeddings))
    if image_embedding_np.size > 0:
        update_faiss_index("image", np.expand_dims(image_embedding_np, axis=0), [report_id])
    if text_embedding_np.size > 0:
        update_faiss_index("text", np.expand_dims(text_embedding_np, axis=0), [report_id])

    # --- 2. Search Existing FAISS Indexes ---
    # This part needs to be more sophisticated to only search against reports of the opposite type.
    # For a prototype, we'll search all available embeddings and filter later.
    
    candidate_matches = {} # Using a dict to easily update scores for a given other_report_id

    # Search logic (simplified):
    if subject_type == "PERSON" and face_embeddings_np.size > 0:
        # Search all existing face embeddings (which might be from LOST or FOUND reports)
        # We need to ensure we only match against opposite report types.
        # This requires fetching metadata for matched_ids, which `search_faiss_index` doesn't provide directly.
        # For prototype, we proceed with general search and filter later.

        for query_face_emb in face_embeddings_np: # For each face in the new report
            scores, matched_ids_from_faiss = search_faiss_index("face", query_face_emb, k=10)
            
            for i, other_report_id in enumerate(matched_ids_from_faiss):
                if other_report_id == report_id: # Don't match a report to itself
                    continue
                
                # Check if the other_report_id is of the opposite type
                # Fetch other report details from Supabase
                other_report_response = await supabase.from_("reports").select("type").eq("id", other_report_id).single().execute()
                other_report_details = other_report_response.data
                if other_report_details and other_report_details["type"] != report_type:
                    current_face_score = scores[i]
                    if other_report_id not in candidate_matches:
                        candidate_matches[other_report_id] = {"face_score": current_face_score}
                    else:
                        candidate_matches[other_report_id]["face_score"] = max(
                            candidate_matches[other_report_id].get("face_score", 0.0), current_face_score
                        )

    if image_embedding_np.size > 0:
        scores, matched_ids_from_faiss = search_faiss_index("image", image_embedding_np, k=10)
        for i, other_report_id in enumerate(matched_ids_from_faiss):
            if other_report_id == report_id:
                continue

            other_report_response = await supabase.from_("reports").select("type").eq("id", other_report_id).single().execute()
            other_report_details = other_report_response.data
            if other_report_details and other_report_details["type"] != report_type:
                current_img_score = scores[i]
                if other_report_id not in candidate_matches:
                    candidate_matches[other_report_id] = {"image_score": current_img_score}
                else:
                    candidate_matches[other_report_id]["image_score"] = max(
                        candidate_matches[other_report_id].get("image_score", 0.0), current_img_score
                    )

    if text_embedding_np.size > 0:
        scores, matched_ids_from_faiss = search_faiss_index("text", text_embedding_np, k=10)
        for i, other_report_id in enumerate(matched_ids_from_faiss):
            if other_report_id == report_id:
                continue

            other_report_response = await supabase.from_("reports").select("type").eq("id", other_report_id).single().execute()
            other_report_details = other_report_response.data
            if other_report_details and other_report_details["type"] != report_type:
                current_text_score = scores[i]
                if other_report_id not in candidate_matches:
                    candidate_matches[other_report_id] = {"text_score": current_text_score}
                else:
                    candidate_matches[other_report_id]["text_score"] = max(
                        candidate_matches[other_report_id].get("text_score", 0.0), current_text_score
                    )

    # --- 3. Calculate Fused Scores and Persist ---
    for other_report_id, scores_dict in candidate_matches.items():
        face_score = scores_dict.get("face_score", 0.0)
        image_score = scores_dict.get("image_score", 0.0)
        text_score = scores_dict.get("text_score", 0.0)

        fused_score = calculate_fused_score(face_score, image_score, text_score)

        threshold = PERSON_MATCH_THRESHOLD if subject_type == "PERSON" else ITEM_MATCH_THRESHOLD

        if fused_score > threshold:
            match_id = str(uuid.uuid4()) # Generate unique ID for the match
            
            # Determine which report is lost and which is found for the match entry
            current_report_is_lost = (report_type == "LOST")
            
            new_match_entry = {
                "id": match_id, # Added the ID field here
                "lost_report_id": report_id if current_report_is_lost else other_report_id,
                "found_report_id": other_report_id if current_report_is_lost else report_id,
                "scores": {"face": face_score, "image": image_score, "text": text_score},
                "fused_score": fused_score,
                "status": "PENDING",
                "created_at": datetime.utcnow().isoformat()
            }
            # Insert into Supabase
            insert_response = supabase.from_("matches").insert([new_match_entry]).execute()
            if insert_response.data:
                print(f"Persisted match {match_id}: {new_match_entry}")
                # Send real-time notification about the new match
                await manager.broadcast(f"New match found for report {report_id}: {match_id}")
            else:
                print(f"Failed to persist match {match_id}: {insert_response.last_error}")
    
    # Return a message indicating the job is done, or a list of new match IDs
    return {"message": f"Matching job completed for report {report_id}"}

