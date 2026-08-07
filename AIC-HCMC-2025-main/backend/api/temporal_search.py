from fastapi import APIRouter, Request
from pydantic import BaseModel
import os
import numpy as np
import json

router = APIRouter()

# =====================
# Load FPS dictionary
# =====================
DATASETS_DIR    = "datasets"
TRANSCRIPT_DIR  = os.path.join(DATASETS_DIR, "transcripts")
FPS_JSON_FILE   = os.path.join(DATASETS_DIR, "fps.json")

with open(FPS_JSON_FILE, "r") as f:
    fps_dict = json.load(f)

# =====================
# Input Schema
# =====================
class TemporalInput(BaseModel):
    text1: str
    text2: str

# =====================
# Utils
# =====================
def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    denom = (np.linalg.norm(vec1) * np.linalg.norm(vec2)) + 1e-10
    return float(np.dot(vec1, vec2) / denom)

def get_transcript(video_name: str, keyframe_index: int) -> str:
    try:
        fps = fps_dict.get(video_name)
        if fps is None:
            return ""

        seconds = int(keyframe_index / fps)
        transcript_path = os.path.join(TRANSCRIPT_DIR, f"{video_name}.json")

        if not os.path.exists(transcript_path):
            return ""

        with open(transcript_path, "r") as f:
            transcript_list = json.load(f)

        idx = seconds // 10
        if 0 <= idx < len(transcript_list):
            return transcript_list[idx].get("transcript", "")
        return ""
    except Exception:
        return ""

# =====================
# Temporal Search API
# =====================
@router.post("/temporal-search/")
async def temporal_search(input: TemporalInput, request: Request):
    print(f"[REQUEST] /temporal-search/ received: {input.dict()}")
    try:
        # Embed query texts
        query_vector_1 = request.app.state.clip14_model.embed(input.text1)
        query_vector_2 = request.app.state.clip14_model.embed(input.text2)

        # Retrieve all scene vectors
        scenes = request.app.state.milvus_scene.query(
            collection_name="scene_vectors",
            output_fields=[
                "video_name", "scene_index",
                "start_frame", "end_frame", "mid_frame",
                "scene_feature_vector"
            ],
            limit=1000  
        )

        # Group by video
        videos = {}
        for scene in scenes:
            vname = scene["video_name"]
            videos.setdefault(vname, []).append(scene)

        for vname in videos:
            videos[vname] = sorted(videos[vname], key=lambda x: x["scene_index"])

        # Compute best consecutive pair per video
        rows = []
        for video_name, scene_list in videos.items():
            best_score, best_pair = -1, None
            for i in range(len(scene_list) - 1):
                s1, s2 = scene_list[i], scene_list[i + 1]
                v1 = np.array(s1["scene_feature_vector"], dtype=np.float32)
                v2 = np.array(s2["scene_feature_vector"], dtype=np.float32)

                score = (cosine_similarity(v1, query_vector_1) +
                         cosine_similarity(v2, query_vector_2)) / 2.0

                if score > best_score:
                    best_score = score
                    best_pair = (s1, s2)

            if best_pair:
                s1, s2 = best_pair
                keyframes = [s1["mid_frame"], s2["mid_frame"]]

                # Get from keyframe database
                youtube_links = []
                keyframe_paths = []
                for k in keyframes:
                    try:
                        results = request.app.state.milvus_keyframe.query(
                            collection_name="keyframe_vectors",
                            filter=f'video_name == "{video_name}" and keyframe_index == "{k}"',
                            output_fields=["keyframe_path", "youtube_url"]
                        )
                    except Exception as e:
                        results = []

                    if results:
                        keyframe_paths.append(results[0].get("keyframe_path", f"datasets/keyframes/{video_name}/{k}.jpg"))
                        youtube_links.append(results[0].get("youtube_url", ""))
                    else:
                        keyframe_paths.append(f"datasets/keyframes/{video_name}/{k}.jpg")
                        youtube_links.append("")

                transcript = get_transcript(video_name, int(keyframes[0]))

                rows.append({
                    "video_name": video_name,
                    "keyframe_paths": keyframe_paths,
                    "keyframes": [str(k) for k in keyframes],
                    "youtube_links": youtube_links,
                    "transcript": transcript,
                    "score": best_score
                })

        return {
            "similar_frames": [],
            "rows": rows
        }

    except Exception as e:
        return {
            "error": f"Failed to process temporal search: {str(e)}",
            "similar_frames": [],
            "rows": []
        }
