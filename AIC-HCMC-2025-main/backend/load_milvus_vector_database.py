from glob import glob
import os
import numpy as np
from pymilvus import MilvusClient, DataType
import json
from tqdm import tqdm
import unicodedata
import re

# Directories containing data
DATASETS_DIR        = "datasets"
# KEYFRAMES_DIR       = os.path.join(DATASETS_DIR, "keyframes")
KEYFRAMES_DIR       = os.path.join("frontend", "src", "assets", "datasets", "keyframes")
CLIP_FEATURES_DIR   = os.path.join(DATASETS_DIR, "clip-features")
MEDIA_INFO_DIR      = os.path.join(DATASETS_DIR, "media-info")
FPS_JSON_FILE       = os.path.join(DATASETS_DIR, "fps.json")
OCR_JSON_DIR        = os.path.join(DATASETS_DIR, "ocr-json")
DATABASES_DIR       = "databases"
DATABASE_PATH       = os.path.join(DATABASES_DIR, "keyframe_vectors.db")
COLLECTION_NAME     = "keyframe_vectors"

with open(FPS_JSON_FILE, "r") as f:
    fps_dict = json.load(f)


def normalize_text(text: str) -> str:
    """Convert text to lowercase and remove accents/diacritics"""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)  # remove accents
    return text


def create_database_dir():
    """Create the database directory if it doesn't exist"""
    os.makedirs(DATABASES_DIR, exist_ok=True)

def initialize_milvus_client():
    """Initialize Milvus client with local .db file"""
    try:
        client = MilvusClient(uri=DATABASE_PATH)
        print(f"[INFO] Initialized Milvus client with database at {DATABASE_PATH}")
        return client
    except Exception as e:
        print(f"[ERROR] Failed to initialize Milvus client: {e}")
        raise

def create_collection(client):
    """Create collection in Milvus if it doesn't exist"""
    if client.has_collection(COLLECTION_NAME):
        print(f"[INFO] Collection {COLLECTION_NAME} already exists, dropping it...")
        client.drop_collection(COLLECTION_NAME)
        print(f"[INFO] Collection {COLLECTION_NAME} dropped successfully")
    
    # Define schema for the collection
    schema = MilvusClient.create_schema(
        auto_id=False,
        enable_dynamic_field=True
    )
    
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="video_name", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="keyframe_index", datatype=DataType.VARCHAR, max_length=50)
    schema.add_field(field_name="keyframe_path", datatype=DataType.VARCHAR, max_length=255)
    schema.add_field(field_name="clip_feature_vector", datatype=DataType.FLOAT_VECTOR, dim=768)
    schema.add_field(field_name="youtube_url", datatype=DataType.VARCHAR, max_length=500)
    schema.add_field(field_name="ocr_text", datatype=DataType.VARCHAR, max_length=2000)
    
    # Create index parameters
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="clip_feature_vector",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 4096}
    )

    # Create collection with schema and index
    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )
    
    print(f"[INFO] Created collection {COLLECTION_NAME} with index")

def load_vectors_to_milvus(client):
    """Scan directories and insert vectors and keyframe paths into Milvus"""
    vectors = []
    video_names = []
    keyframe_indices = []
    keyframe_paths = []
    ids = []
    youtube_urls = []
    ocr_texts = []
    
    # Scan all subdirectories in clip-features
    for video_dir in glob(os.path.join(CLIP_FEATURES_DIR, "*/")):
        video_name = os.path.basename(os.path.dirname(video_dir))  # e.g., L01_V001
        
        # Load media-info json for this video
        media_info_path = os.path.join(MEDIA_INFO_DIR, f"{video_name}.json")
        if not os.path.exists(media_info_path):
            print(f"[WARNING] Media info file {media_info_path} not found, skipping youtube_url")
            watch_url = None
        else:
            try:
                with open(media_info_path, "r") as f:
                    media_info = json.load(f)
                watch_url = media_info.get("watch_url", None)
            except Exception as e:
                print(f"[WARNING] Failed to read media info {media_info_path}: {e}")
                watch_url = None

        # Load OCR json for this video
        ocr_path = os.path.join(OCR_JSON_DIR, f"{video_name}.json")
        if os.path.exists(ocr_path):
            try:
                with open(ocr_path, "r") as f:
                    ocr_dict = json.load(f)
            except Exception as e:
                print(f"[WARNING] Failed to load OCR json {ocr_path}: {e}")
                ocr_dict = {}
        else:
            ocr_dict = {}
            print(f"[INFO] No OCR json found for {video_name}, proceeding without OCR data")

        # Corresponding keyframe directory
        keyframe_video_dir = os.path.join(KEYFRAMES_DIR, video_name)
        if not os.path.exists(keyframe_video_dir):
            print(f"[WARNING] Keyframe directory {keyframe_video_dir} does not exist, skipping")
            continue
        
        # Scan .npy files in the video directory
        for npy_file in glob(os.path.join(video_dir, "*.npy")):
            keyframe_index = os.path.splitext(os.path.basename(npy_file))[0]  # e.g., 1234
            
            # Load vector from .npy file
            vector = np.load(npy_file)
            vector = vector.squeeze(0)      # (1, 768) -> (768,)
            if vector.shape != (768,):
                print(f"[WARNING] Skipping {npy_file}: Invalid shape {vector.shape}")
                continue
            
            # Check if corresponding image exists
            image_file = os.path.join(keyframe_video_dir, f"{keyframe_index}.jpg")
            if not os.path.exists(image_file):
                print(f"[WARNING] Image {image_file} not found, skipping")
                continue
            
            # Store relative path to image
            keyframe_path = "datasets" + image_file.split("datasets", 1)[1]
            
            # Compute youtube_url
            fps = fps_dict.get(video_name, None)
            if fps is not None and watch_url:
                try:
                    frame_idx = int(keyframe_index)
                    seconds = int(frame_idx / fps)
                    youtube_url = f"{watch_url}&t={seconds}s"
                except Exception as e:
                    print(f"[WARNING] Failed to compute youtube_url for {video_name} frame {keyframe_index}: {e}")
                    youtube_url = None
            else:
                youtube_url = None

            ocr_list = ocr_dict.get(f"{keyframe_index}", [])
            ocr_text = " *=*=* ".join([normalize_text(w) for w in ocr_list])
            
            # Append all data
            vectors.append(vector.tolist())  
            video_names.append(video_name)
            keyframe_indices.append(keyframe_index)
            keyframe_paths.append(keyframe_path)
            youtube_urls.append(youtube_url)
            ocr_texts.append(ocr_text)
    
    if not vectors:
        print("[WARNING] No vectors or keyframes found to insert")
        return
    
    # Generate IDs for each entry
    ids = list(range(1, len(vectors) + 1))
    
    # Prepare data
    rows = []
    for i in tqdm(range(len(vectors)), desc="Preparing data for insertion"):
        rows.append({
            "id": ids[i],
            "video_name": video_names[i],
            "keyframe_index": keyframe_indices[i],
            "keyframe_path": keyframe_paths[i],
            "clip_feature_vector": vectors[i],
            "youtube_url": youtube_urls[i],
            "ocr_text": ocr_texts[i]
        })

    # Insert data into Milvus
    try:
        batch_size = 1000
        for i in tqdm(range(0, len(rows), batch_size), desc="Inserting batches"):
            batch = rows[i:i + batch_size]
            client.insert(
                collection_name=COLLECTION_NAME,
                data=batch
            )
        print(f"[INFO] Inserted {len(vectors)} vectors with keyframe paths into Milvus")
    except Exception as e:
        print(f"[ERROR] Failed to insert data into Milvus: {e}")
        raise
    
    # Load collection for search readiness
    client.load_collection(COLLECTION_NAME)
    print(f"[INFO] Collection {COLLECTION_NAME} loaded and ready for search")

def main():
    # Create database directory
    create_database_dir()
    
    # Initialize Milvus client
    client = initialize_milvus_client()
    
    # Create collection
    create_collection(client)
    
    # Load vectors and keyframe paths into Milvus
    load_vectors_to_milvus(client)
    
    print(f"[INFO] Data loading completed. Database saved at {DATABASE_PATH}")

if __name__ == "__main__":
    main()