from glob import glob
import os
import numpy as np
from pymilvus import MilvusClient, DataType
import json
from tqdm import tqdm

# Directories
DATASETS_DIR        = "datasets"
SCENE_TXT_DIR       = os.path.join(DATASETS_DIR, "transnetv2-scenes")
CLIP_FEATURES_DIR   = os.path.join(DATASETS_DIR, "clip-features")
DATABASES_DIR       = "databases"
DATABASE_PATH       = os.path.join(DATABASES_DIR, "scene_vectors.db")
COLLECTION_NAME     = "scene_vectors"


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
    """Create collection for scene vectors"""
    if client.has_collection(COLLECTION_NAME):
        print(f"[INFO] Collection {COLLECTION_NAME} already exists, dropping it...")
        client.drop_collection(COLLECTION_NAME)
        print(f"[INFO] Collection {COLLECTION_NAME} dropped successfully")
    
    # Define schema
    schema = MilvusClient.create_schema(
        auto_id=False,
        enable_dynamic_field=True
    )
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("video_name", DataType.VARCHAR, max_length=100)
    schema.add_field("scene_index", DataType.INT64)
    schema.add_field("start_frame", DataType.INT64)
    schema.add_field("end_frame", DataType.INT64)
    schema.add_field("mid_frame", DataType.INT64)
    schema.add_field("scene_feature_vector", DataType.FLOAT_VECTOR, dim=768)

    # Index params
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="scene_feature_vector",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128}
    )

    # Create collection
    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )
    print(f"[INFO] Created collection {COLLECTION_NAME} with index")


def load_scenes_to_milvus(client):
    """Read .scenes.txt, pick mid frame vector, insert into Milvus"""
    rows = []
    scene_id = 1

    for txt_file in glob(os.path.join(SCENE_TXT_DIR, "*.scenes.txt")):
        video_name = os.path.basename(txt_file).replace(".mp4.scenes.txt", "")

        with open(txt_file, "r") as f:
            lines = f.readlines()

        for scene_index, line in enumerate(lines):
            try:
                start, end = map(int, line.strip().split())
                mid = (start + end) // 2
                npy_file = os.path.join(CLIP_FEATURES_DIR, video_name, f"{mid}.npy")

                if not os.path.exists(npy_file):
                    print(f"[WARNING] Missing mid-frame vector {npy_file}, skip scene")
                    continue

                vec = np.load(npy_file).squeeze()
                if vec.shape != (768,):
                    print(f"[WARNING] Invalid shape {vec.shape} for {npy_file}, skip scene")
                    continue

                rows.append({
                    "id": scene_id,
                    "video_name": video_name,
                    "scene_index": scene_index,
                    "start_frame": start,
                    "end_frame": end,
                    "mid_frame": mid,
                    "scene_feature_vector": vec.tolist()
                })
                scene_id += 1
            except Exception as e:
                print(f"[ERROR] Failed parsing scene in {txt_file}: {e}")
                continue

    if not rows:
        print("[WARNING] No scene vectors found to insert")
        return

    # Insert batch
    try:
        batch_size = 1000
        for i in tqdm(range(0, len(rows), batch_size), desc="Inserting scene batches"):
            batch = rows[i:i + batch_size]
            client.insert(
                collection_name=COLLECTION_NAME,
                data=batch
            )
        print(f"[INFO] Inserted {len(rows)} scenes into Milvus")
    except Exception as e:
        print(f"[ERROR] Failed to insert scene data into Milvus: {e}")
        raise

    client.load_collection(COLLECTION_NAME)
    print(f"[INFO] Collection {COLLECTION_NAME} loaded and ready for search")


def main():
    create_database_dir()
    client = initialize_milvus_client()
    create_collection(client)
    load_scenes_to_milvus(client)
    print(f"[INFO] Scene data loading completed. Database saved at {DATABASE_PATH}")


if __name__ == "__main__":
    main()
