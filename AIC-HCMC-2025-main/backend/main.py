from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import health_check, quick_search, translate_vi_to_en, submit, temporal_search
from backend.clip_vit_large_14_model import CLIP_ViT_L_14
from backend.vietnamese_to_english_translator import VietnameseToEnglishTranslator
import os
from pymilvus import MilvusClient

os.makedirs("submission", exist_ok=True)

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    app.state.clip14_model = CLIP_ViT_L_14()
    app.state.vi_to_en_translator = VietnameseToEnglishTranslator()


    # # Milvus databases
    # try:
    #     db_path_scene = os.path.join("databases", "scene_vectors.db")
    #     app.state.milvus_scene = MilvusClient(uri=db_path_scene)
    #     app.state.milvus_scene.load_collection("scene_vectors")
    #     print(f"[INFO] Milvus client loaded scene_vectors from {db_path_scene}")
    # except Exception as e:
    #     print(f"[ERROR] Failed to initialize scene_vectors: {e}")
    #     raise

    try:
        db_path_keyframe = os.path.join("databases", "keyframe_vectors.db")
        app.state.milvus_keyframe = MilvusClient(uri=db_path_keyframe)
        app.state.milvus_keyframe.load_collection("keyframe_vectors")
        print(f"[INFO] Milvus client loaded keyframe_vectors from {db_path_keyframe}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize keyframe_vectors: {e}")
        raise

# Import routers
app.include_router(health_check.router)
app.include_router(quick_search.router)
app.include_router(translate_vi_to_en.router)
app.include_router(submit.router)
app.include_router(temporal_search.router)
