import numpy as np
from typing import List, Optional, Union
from PIL import Image
from io import BytesIO
import base64

# For Face Embeddings
try:
    # from deepface import DeepFace # Commented out due to temporary ML library disable
    # DeepFace models: 'VGG-Face', 'Facenet', 'Facenet512', 'OpenFace', 'DeepFace', 'DeepID', 'ArcFace', 'Dlib', 'SFace'
    FACE_MODEL_NAME = "ArcFace"
except ImportError:
    print("DeepFace not installed. Face recognition will be unavailable.")
    DeepFace = None

# For Image Embeddings (CLIP)
try:
    # from transformers import CLIPProcessor, CLIPModel # Commented out due to temporary ML library disable
    # import torch # Commented out due to temporary ML library disable
    # Load CLIP model and processor
    CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
    clip_model = None # Set to None as a placeholder
    clip_processor = None # Set to None as a placeholder
    CLIP_DEVICE = "cpu" # Default to cpu
except ImportError:
    print("Hugging Face Transformers or Torch not installed. CLIP image embeddings will be unavailable.")
    clip_model = None
    clip_processor = None

# For Text Embeddings (Sentence-Transformers)
try:
    from sentence_transformers import SentenceTransformer # Uncommented for multilingual text embeddings
    SBERT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    sbert_model = SentenceTransformer(SBERT_MODEL_NAME) # Initialize the model
except ImportError:
    print("Sentence-Transformers not installed. Text embeddings will be unavailable.")
    sbert_model = None

def get_face_embeddings(image_base64_list: List[str]) -> List[List[float]]:
    """
    Generates face embeddings for all detected faces in a list of images.
    Each image is provided as a base64 encoded string.
    """
    if DeepFace is None:
        return []

    face_embeddings = []
    for img_b64 in image_base64_list:
        try:
            # Decode base64 to image
            img_bytes = base64.b64decode(img_b64)
            img_stream = BytesIO(img_bytes)
            img_np = np.array(Image.open(img_stream))

            # Extract face embeddings. DeepFace can return multiple faces per image.
            # We will take the embedding for each detected face.
            # This is a simplified approach; in a real scenario, you might want to
            # select the main face or handle multiple faces more explicitly.
            # representations = DeepFace.represent(img_path=img_np, model_name=FACE_MODEL_NAME, enforce_detection=False) # DeepFace is commented out
            representations = [] # Placeholder since DeepFace is commented out
            if representations:
                for rep in representations:
                    face_embeddings.append(rep["embedding"])
        except Exception as e:
            print(f"Error processing face for an image: {e}")
            continue
    return face_embeddings

def get_image_embedding(image_base64: str) -> Optional[List[float]]:
    """
    Generates a single CLIP image embedding for an item image.
    The image is provided as a base64 encoded string.
    """
    if clip_model is None or clip_processor is None:
        return None
    try:
        img_bytes = base64.b64decode(image_base64)
        img_stream = BytesIO(img_bytes)
        image = Image.open(img_stream)

        # inputs = clip_processor(images=image, return_tensors="pt").to(CLIP_DEVICE) # CLIP is commented out
        # with torch.no_grad(): # Torch is commented out
        #     image_features = clip_model.get_image_features(**inputs) # CLIP is commented out
        # return image_features.squeeze().cpu().numpy().tolist() # CLIP is commented out
        return [0.0] * 512 # Placeholder for CLIP embedding
    except Exception as e:
        print(f"Error processing image for CLIP embedding: {e}")
        return None

def get_text_embedding(text: str, language: str = "en") -> Optional[List[float]]:
    """
    Generates a multilingual text embedding for a description.
    """
    if sbert_model is None:
        return None
    try:
        # Sentence-transformers are already multilingual with this model
        embeddings = sbert_model.encode(text) # SBERT is uncommented
        return embeddings.tolist() # SBERT is uncommented
    except Exception as e:
        print(f"Error processing text for SBERT embedding: {e}")
        return None

def calculate_fused_score(face_score: float, img_score: float, text_score: float) -> float:
    """
    Calculates the fused score based on the given weights.
    Pseudocode: fused = 0.5*face + 0.3*image + 0.2*text
    """
    return (0.5 * face_score) + (0.3 * img_score) + (0.2 * text_score)
