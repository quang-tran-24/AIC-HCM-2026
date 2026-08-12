import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymilvus import MilvusClient

from backend.api import health_check, quick_search, translate_vi_to_en, submit, temporal_search, qa_search, trake_search
from backend.clip_vit_large_14_model import CLIP_ViT_L_14
from backend.vietnamese_to_english_translator import VietnameseToEnglishTranslator
from backend.qa_answer import QwenVLAnswerer

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
    app.state.qwen_vl_answerer = QwenVLAnswerer()

    with open(os.path.join("datasets", "fps.json"), "r", encoding="utf-8") as f:
        app.state.fps_dict = json.load(f)

    # keyframe_vectors is required for KIS/Q&A -- fail loudly if it's missing, the app
    # is useless without it.
    db_path_keyframe = os.path.join("databases", "keyframe_vectors.db")
    app.state.milvus_keyframe = MilvusClient(uri=db_path_keyframe)
    app.state.milvus_keyframe.load_collection("keyframe_vectors")
    print(f"[INFO] Milvus client loaded keyframe_vectors from {db_path_keyframe}")

    # scene_vectors is ONLY needed for TRAKE -- warn and continue instead of crashing the
    # whole server if it's not built yet, so KIS/Q&A stay usable while TRAKE data catches up.
    # Run `python3 backend/load_scene_vector_database.py` (server stopped) to build it.
    app.state.milvus_scene = None
    try:
        db_path_scene = os.path.join("databases", "scene_vectors.db")
        milvus_scene = MilvusClient(uri=db_path_scene)
        milvus_scene.load_collection("scene_vectors")
        app.state.milvus_scene = milvus_scene
        print(f"[INFO] Milvus client loaded scene_vectors from {db_path_scene}")
    except Exception as e:
        print(f"[WARN] scene_vectors not available ({e}) -- TRAKE search will be disabled "
              f"until you run: python3 backend/load_scene_vector_database.py")

# Import routers
app.include_router(health_check.router)
app.include_router(quick_search.router)
app.include_router(translate_vi_to_en.router)
app.include_router(submit.router)
app.include_router(temporal_search.router)
app.include_router(qa_search.router)
app.include_router(trake_search.router)