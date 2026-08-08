from fastapi import APIRouter, Request
from pydantic import BaseModel
import re
import os
import numpy as np
from typing import List, Optional, Dict
from rapidfuzz import fuzz
import json
import unicodedata
from glob import glob
from backend.rerank import rerank_candidates # New file to reranking

router = APIRouter()

DATASETS_DIR        = "datasets"
TRANSCRIPT_DIR      = os.path.join(DATASETS_DIR, "transcripts")
OCR_DIR             = os.path.join(DATASETS_DIR, "ocr-json")
FPS_JSON_FILE       = os.path.join(DATASETS_DIR, "fps.json")
# CLIP_FEATURES_DIR   = os.path.join(DATASETS_DIR, "clip-features")
with open(FPS_JSON_FILE, "r") as f:
    fps_dict = json.load(f)

TRANSCRIPT_FILES = [
    fname for fname in os.listdir(TRANSCRIPT_DIR)
    if fname.lower().endswith(".json")
]
TRANSCRIPT_VIDEO_NAMES = [os.path.splitext(fname)[0] for fname in TRANSCRIPT_FILES]
TRANSCRIPT_CACHE: Dict[str, List[dict]] = {}
KEYFRAME_CACHE: Dict[str, List[dict]] = {}
# Global cache for keyframe info: (video_name, keyframe_index) -> keyframe_info
KEYFRAME_INFO_CACHE: Dict[tuple, dict] = {}
KEYFRAME_INFO_LOADED = False

# Pre-load all transcripts into memory for fast search
ALL_TRANSCRIPT_SEGMENTS: List[dict] = []
print("[INFO] Loading all transcripts into memory...")
for video_name in TRANSCRIPT_VIDEO_NAMES:
    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{video_name}.json")
    if not os.path.exists(transcript_path):
        continue
    try:
        with open(transcript_path, "r") as f:
            segments = json.load(f)
        fps = fps_dict.get(video_name)
        if not fps:
            continue
        for segment in segments:
            segment_text = segment.get("transcript", "")
            if segment_text:
                ALL_TRANSCRIPT_SEGMENTS.append({
                    "video_name": video_name,
                    "transcript": segment_text,
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0),
                    "fps": fps,
                })
    except Exception as e:
        print(f"[WARN] Failed to load transcript for {video_name}: {e}")
        continue

print(f"[INFO] Loaded {len(ALL_TRANSCRIPT_SEGMENTS)} transcript segments into memory")

# Pre-load all OCR data into memory for fast search
OCR_FILES = [
    fname for fname in os.listdir(OCR_DIR)
    if fname.lower().endswith(".json")
]
OCR_VIDEO_NAMES = [os.path.splitext(fname)[0] for fname in OCR_FILES]
ALL_OCR_SEGMENTS: List[dict] = []
print("[INFO] Loading all OCR data into memory...")
for video_name in OCR_VIDEO_NAMES:
    ocr_path = os.path.join(OCR_DIR, f"{video_name}.json")
    if not os.path.exists(ocr_path):
        continue
    try:
        with open(ocr_path, "r") as f:
            ocr_data = json.load(f)
        fps = fps_dict.get(video_name)
        if not fps:
            continue
        for keyframe_idx_str, ocr_lines in ocr_data.items():
            if not ocr_lines or not isinstance(ocr_lines, list):
                continue
            # Join all OCR lines into a single text
            ocr_text = " ".join(str(line) for line in ocr_lines if line)
            if ocr_text:
                try:
                    keyframe_idx = int(keyframe_idx_str)
                except (ValueError, TypeError):
                    continue
                ALL_OCR_SEGMENTS.append({
                    "video_name": video_name,
                    "ocr_text": ocr_text,
                    "keyframe_index": keyframe_idx,
                    "fps": fps,
                })
    except Exception as e:
        print(f"[WARN] Failed to load OCR for {video_name}: {e}")
        continue

print(f"[INFO] Loaded {len(ALL_OCR_SEGMENTS)} OCR segments into memory")

# VIDEO_KEYFRAMES_MAP = {}
# npy_files = glob(os.path.join(CLIP_FEATURES_DIR, "*", "*.npy"))
# for npy_file in npy_files:
#     video_name = os.path.basename(os.path.dirname(npy_file))
#     keyframe = os.path.basename(npy_file).rsplit('.', 1)[0]
#     if video_name not in VIDEO_KEYFRAMES_MAP:
#         VIDEO_KEYFRAMES_MAP[video_name] = []
#     VIDEO_KEYFRAMES_MAP[video_name].append(int(keyframe))

# for video_name in VIDEO_KEYFRAMES_MAP:
#     VIDEO_KEYFRAMES_MAP[video_name].sort()
#     keyframes = VIDEO_KEYFRAMES_MAP[video_name]
#     VIDEO_KEYFRAMES_MAP[video_name] = [str(k) for k in keyframes]
    


# =====================
# Ultility Functions
# =====================

def get_transcript(video_name: str, keyframe_index: int) -> str:
    """Return the closest transcript segment for the given keyframe."""
    try:        
        fps = fps_dict.get(video_name)

        seconds = int(keyframe_index / fps)
        transcript_path = os.path.join(TRANSCRIPT_DIR, f"{video_name}.json")
        
        if not os.path.exists(transcript_path):
            return None
        
        with open(transcript_path, "r") as f:
            transcript_list = json.load(f)
        
        idx = seconds // 10
        before = transcript_list[idx - 1]["transcript"] if (0 <= idx - 1 < len(transcript_list)) else ""
        main   = transcript_list[idx]["transcript"]      if (0 <= idx < len(transcript_list)) else ""
        after  = transcript_list[idx + 1]["transcript"]  if (0 <= idx + 1 < len(transcript_list)) else ""

        return f"{before} {main} {after}".strip()
    except Exception as e:
        print(idx)

        print(len(transcript_list))

        print(f"[ERROR] get_transcript failed for {video_name}: {e}")
        return None
    
def process_keyframe_path(keyframe_path):
    filename = keyframe_path.split('/')[-1]
    name_without_ext = filename.rsplit('.', 1)[0]
    return name_without_ext

def strip_accents(s: str) -> str:
    """Remove accents, convert to lowercase, and normalize d/đ"""
    # Replace đ/Đ with d/D first
    s = s.replace('đ', 'd').replace('Đ', 'D')
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower().strip()

def is_text_match(text1: str, text2: str, threshold: int = 50) -> int:
    """
    - Remove accents and lowercase both text1 and text2
    - Split text1 into parts separated by commas
    - If any part is a direct substring of text2 → return (số lần xuất hiện * 100)
    - Otherwise use fuzzy partial_ratio with threshold
    """
    t2 = strip_accents(text2)
    for part in text1.split(", "):
        t1_part = strip_accents(part)
        if not t1_part:
            continue
        count = t2.count(t1_part)
        if count > 0:
            return count * 100
        # Fuzzy partial ratio
        score = fuzz.partial_ratio(t1_part, t2)
        if score >= threshold:
            return score
    return 0

def exact_text_match(query: str, text: str) -> bool:
    """Check if query text exists exactly (case-insensitive, accent-insensitive) in text"""
    query_normalized = strip_accents(query)
    text_normalized = strip_accents(text)
    return query_normalized in text_normalized

def load_transcript_segments(video_name: str) -> List[dict]:
    if video_name in TRANSCRIPT_CACHE:
        return TRANSCRIPT_CACHE[video_name]

    transcript_path = os.path.join(TRANSCRIPT_DIR, f"{video_name}.json")
    if not os.path.exists(transcript_path):
        TRANSCRIPT_CACHE[video_name] = []
        return []

    try:
        with open(transcript_path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load transcript for {video_name}: {e}")
        data = []

    TRANSCRIPT_CACHE[video_name] = data
    return data


def get_video_keyframes(video_name: str, request: Request) -> List[dict]:
    if video_name in KEYFRAME_CACHE:
        return KEYFRAME_CACHE[video_name]

    try:
        results = request.app.state.milvus_keyframe.query(
            collection_name="keyframe_vectors",
            filter=f'video_name == "{video_name}"',
            output_fields=["video_name", "keyframe_path", "youtube_url", "ocr_text", "keyframe_index"]
        )
    except Exception as e:
        print(f"[ERROR] Failed to fetch keyframes for {video_name}: {e}")
        KEYFRAME_CACHE[video_name] = []
        return []

    formatted = []
    for item in results or []:
        try:
            idx = int(item.get("keyframe_index"))
        except (TypeError, ValueError):
            continue
        formatted.append({
            "video_name": item.get("video_name"),
            "keyframe_path": item.get("keyframe_path"),
            "youtube_url": item.get("youtube_url"),
            "ocr_text": item.get("ocr_text") or "",
            "keyframe_index": idx,
        })

    formatted.sort(key=lambda x: x["keyframe_index"])
    KEYFRAME_CACHE[video_name] = formatted
    return formatted


def preload_keyframe_info_cache(request: Request):
    """Pre-load all keyframe info from Milvus into cache"""
    global KEYFRAME_INFO_CACHE, KEYFRAME_INFO_LOADED
    
    if KEYFRAME_INFO_LOADED:
        return
    
    print("[INFO] Pre-loading keyframe info from Milvus...")
    try:
        # Get all unique video names from transcripts and OCR
        all_video_names = set(TRANSCRIPT_VIDEO_NAMES + OCR_VIDEO_NAMES)
        
        for video_name in all_video_names:
            try:
                results = request.app.state.milvus_keyframe.query(
                    collection_name="keyframe_vectors",
                    filter=f'video_name == "{video_name}"',
                    output_fields=["video_name", "keyframe_path", "youtube_url", "ocr_text", "keyframe_index"]
                )
                for item in results or []:
                    try:
                        idx = int(item.get("keyframe_index"))
                        key = (video_name, idx)
                        KEYFRAME_INFO_CACHE[key] = {
                            "video_name": item.get("video_name"),
                            "keyframe_path": item.get("keyframe_path"),
                            "youtube_url": item.get("youtube_url"),
                            "ocr_text": item.get("ocr_text") or "",
                            "keyframe_index": idx,
                        }
                    except (TypeError, ValueError):
                        continue
            except Exception as e:
                print(f"[WARN] Failed to load keyframes for {video_name}: {e}")
                continue
        
        KEYFRAME_INFO_LOADED = True
        print(f"[INFO] Pre-loaded {len(KEYFRAME_INFO_CACHE)} keyframe info entries into cache")
    except Exception as e:
        print(f"[ERROR] Failed to pre-load keyframe info: {e}")


def get_keyframe_info(video_name: str, keyframe_index: int, request: Request) -> Optional[dict]:
    """Get keyframe info from cache or Milvus"""
    global KEYFRAME_INFO_CACHE, KEYFRAME_INFO_LOADED
    
    # Pre-load cache on first access
    if not KEYFRAME_INFO_LOADED:
        preload_keyframe_info_cache(request)
    
    key = (video_name, keyframe_index)
    if key in KEYFRAME_INFO_CACHE:
        return KEYFRAME_INFO_CACHE[key]
    
    # Fallback: query Milvus if not in cache
    try:
        results = request.app.state.milvus_keyframe.query(
            collection_name="keyframe_vectors",
            filter=f'video_name == "{video_name}" AND keyframe_index == {keyframe_index}',
            output_fields=["video_name", "keyframe_path", "youtube_url", "ocr_text", "keyframe_index"]
        )
        if results:
            item = results[0]
            info = {
                "video_name": item.get("video_name"),
                "keyframe_path": item.get("keyframe_path"),
                "youtube_url": item.get("youtube_url"),
                "ocr_text": item.get("ocr_text") or "",
                "keyframe_index": int(item.get("keyframe_index")),
            }
            KEYFRAME_INFO_CACHE[key] = info
            return info
    except Exception as e:
        print(f"[WARN] Failed to fetch keyframe info for {video_name}:{keyframe_index}: {e}")
    
    return None


def get_keyframe_near(video_name: str, target_idx: int, request: Request) -> Optional[dict]:
    """Get nearest keyframe to target index"""
    keyframes = get_video_keyframes(video_name, request)
    if not keyframes:
        return None

    nearest = min(keyframes, key=lambda x: abs(x["keyframe_index"] - target_idx))
    # Return from cache if available
    return get_keyframe_info(video_name, nearest["keyframe_index"], request) or nearest


def transcript_only_search(transcript_query: str, ocr_query: str, request: Request, mode: int) -> dict:
    transcript_query = (transcript_query or "").strip()
    ocr_query = (ocr_query or "").strip()

    if not transcript_query:
        return {
            "error": "Transcript text is required for transcript-only search",
            "similar_frames": [],
            "rows": []
        }

    match_map: Dict[tuple, dict] = {}

    # Search through pre-loaded segments
    for segment in ALL_TRANSCRIPT_SEGMENTS:
        video_name = segment["video_name"]
        
        # Filter by mode
        if mode == 1 and not video_name.startswith("L26_"):
            continue
        if mode == 2 and not video_name.startswith("L25_"):
            continue

        segment_text = segment["transcript"]
        if not segment_text:
            continue

        # Exact match check
        if not exact_text_match(transcript_query, segment_text):
            continue

        # Calculate target keyframe index
        start = segment.get("start", 0)
        end = segment.get("end", start + 10)
        midpoint_sec = (start + end) / 2
        fps = segment["fps"]
        target_idx = int(midpoint_sec * fps)

        keyframe_info = get_keyframe_near(video_name, target_idx, request)
        if not keyframe_info:
            continue

        ocr_score = 0
        if ocr_query:
            ocr_score = is_text_match(ocr_query, keyframe_info.get("ocr_text", ""))
            if ocr_score <= 0:
                continue

        key = (video_name, keyframe_info.get("keyframe_index"))
        existing = match_map.get(key)

        # Get full transcript context (current + before + after segments)
        full_transcript = segment_text
        segments_list = load_transcript_segments(video_name)
        if segments_list:
            segment_idx = next((i for i, s in enumerate(segments_list) 
                              if s.get("transcript", "") == segment_text), None)
            if segment_idx is not None:
                before = segments_list[segment_idx - 1]["transcript"] if segment_idx > 0 else ""
                after = segments_list[segment_idx + 1]["transcript"] if segment_idx < len(segments_list) - 1 else ""
                full_transcript = f"{before} {segment_text} {after}".strip()

        payload = {
            "video_name": video_name,
            "keyframe_path": keyframe_info.get("keyframe_path"),
            "keyframe_index": keyframe_info.get("keyframe_index"),
            "youtube_url": keyframe_info.get("youtube_url"),
            "transcript": full_transcript,
            "transcript_score": 100,  # Exact match = 100
            "ocr_text": keyframe_info.get("ocr_text", ""),
            "ocr_score": ocr_score,
        }

        if existing is None:
            match_map[key] = payload

    matches = list(match_map.values())

    if not matches:
        return {
            "similar_frames": [],
            "rows": []
        }

    matches.sort(key=lambda x: (x["transcript_score"], x["ocr_score"]), reverse=True)

    similar_frames = []
    for item in matches[:50]:
        similar_frames.append({
            "video_name": item["video_name"],
            "keyframe_path": item["keyframe_path"],
            "keyframe": item["keyframe_index"],
            "youtube_url": item.get("youtube_url"),
            "similarity_score": item["transcript_score"],
        })

    rows_map: Dict[str, List[dict]] = {}
    for item in matches:
        rows_map.setdefault(item["video_name"], []).append(item)

    rows = []
    for video_name, items in rows_map.items():
        items = sorted(items, key=lambda x: x["keyframe_index"])[:20]
        keyframe_paths = [i["keyframe_path"] for i in items]
        keyframes = [str(i["keyframe_index"]) for i in items]
        youtube_links = [i.get("youtube_url") for i in items]
        ocr_texts = [i.get("ocr_text", "") for i in items]
        ocr_score = max((i.get("ocr_score", 0) for i in items), default=0)
        best_transcript = max(items, key=lambda x: x["transcript_score"])

        rows.append({
            "video_name": video_name,
            "keyframe_paths": keyframe_paths,
            "keyframes": keyframes,
            "youtube_links": youtube_links,
            "ocr_text": ocr_texts,
            "ocr_score": ocr_score,
            "transcript": best_transcript.get("transcript", ""),
            "transcript_score": best_transcript.get("transcript_score", 0),
        })

    rows.sort(key=lambda x: (x["transcript_score"], x["ocr_score"], len(x["keyframes"])), reverse=True)

    return {
        "similar_frames": similar_frames,
        "rows": rows
    }


def ocr_only_search(ocr_query: str, transcript_query: str, request: Request, mode: int) -> dict:
    ocr_query = (ocr_query or "").strip()
    transcript_query = (transcript_query or "").strip()

    if not ocr_query:
        return {
            "error": "OCR text is required for OCR-only search",
            "similar_frames": [],
            "rows": []
        }

    match_map: Dict[tuple, dict] = {}

    # Search through pre-loaded OCR segments
    for ocr_segment in ALL_OCR_SEGMENTS:
        video_name = ocr_segment["video_name"]
        
        # Filter by mode
        if mode == 1 and not video_name.startswith("L26_"):
            continue
        if mode == 2 and not video_name.startswith("L25_"):
            continue

        ocr_text = ocr_segment["ocr_text"]
        if not ocr_text:
            continue

        # Exact match check
        if not exact_text_match(ocr_query, ocr_text):
            continue

        keyframe_idx = ocr_segment["keyframe_index"]

        # Get keyframe info from cache
        keyframe_info = get_keyframe_info(video_name, keyframe_idx, request)
        if not keyframe_info:
            continue

        # Check transcript if provided
        transcript_score = 0
        full_transcript = ""
        if transcript_query:
            transcript = get_transcript(video_name, keyframe_idx) or ""
            if transcript:
                transcript_score = is_text_match(transcript_query, transcript)
                if transcript_score <= 0:
                    continue
                full_transcript = transcript
        else:
            full_transcript = get_transcript(video_name, keyframe_idx) or ""

        key = (video_name, keyframe_idx)
        existing = match_map.get(key)

        payload = {
            "video_name": video_name,
            "keyframe_path": keyframe_info.get("keyframe_path"),
            "keyframe_index": keyframe_idx,
            "youtube_url": keyframe_info.get("youtube_url"),
            "ocr_text": ocr_text,
            "ocr_score": 100,  # Exact match = 100
            "transcript": full_transcript,
            "transcript_score": transcript_score,
        }

        if existing is None:
            match_map[key] = payload

    matches = list(match_map.values())

    if not matches:
        return {
            "similar_frames": [],
            "rows": []
        }

    matches.sort(key=lambda x: (x["ocr_score"], x["transcript_score"]), reverse=True)

    similar_frames = []
    for item in matches[:50]:
        similar_frames.append({
            "video_name": item["video_name"],
            "keyframe_path": item["keyframe_path"],
            "keyframe": item["keyframe_index"],
            "youtube_url": item.get("youtube_url"),
            "similarity_score": item["ocr_score"],
        })

    rows_map: Dict[str, List[dict]] = {}
    for item in matches:
        rows_map.setdefault(item["video_name"], []).append(item)

    rows = []
    for video_name, items in rows_map.items():
        items = sorted(items, key=lambda x: x["keyframe_index"])[:20]
        keyframe_paths = [i["keyframe_path"] for i in items]
        keyframes = [str(i["keyframe_index"]) for i in items]
        youtube_links = [i.get("youtube_url") for i in items]
        ocr_texts = [i.get("ocr_text", "") for i in items]
        ocr_score = max((i.get("ocr_score", 0) for i in items), default=0)
        best_item = max(items, key=lambda x: x["ocr_score"])

        rows.append({
            "video_name": video_name,
            "keyframe_paths": keyframe_paths,
            "keyframes": keyframes,
            "youtube_links": youtube_links,
            "ocr_text": ocr_texts,
            "ocr_score": ocr_score,
            "transcript": best_item.get("transcript", ""),
            "transcript_score": best_item.get("transcript_score", 0),
        })

    rows.sort(key=lambda x: (x["ocr_score"], x["transcript_score"], len(x["keyframes"])), reverse=True)

    return {
        "similar_frames": similar_frames,
        "rows": rows
    }


# =====================
# Quick Search
# =====================
class SearchInput(BaseModel):
    text: Optional[str] = None
    transcript: Optional[str] = None
    ocr: Optional[str] = None
    


@router.post("/quick-search/")
async def wrapper_quick_search(input: SearchInput, request: Request):
    return await process_text(input, request, mode=0)

@router.post("/quick-search-l26/")
async def wrapper_quick_search_l14(input: SearchInput, request: Request):
    return await process_text(input, request, mode=1)

@router.post("/quick-search-l25/")
async def wrapper_quick_search_l25(input: SearchInput, request: Request):
    return await process_text(input, request, mode=2)

async def process_text(input: SearchInput, request: Request, mode: int):
    print(f"[REQUEST] /quick-search/ received: {input.dict()}")
    try:
        # Pre-load keyframe info cache on first request
        if not KEYFRAME_INFO_LOADED:
            preload_keyframe_info_cache(request)
        
        text_query = (input.text or "").strip()
        transcript_query = (input.transcript or "").strip()
        ocr_query = (input.ocr or "").strip()

        if not text_query:
            if transcript_query:
                return transcript_only_search(transcript_query, ocr_query, request, mode)
            elif ocr_query:
                return ocr_only_search(ocr_query, transcript_query, request, mode)
            else:
                return {
                    "error": "Query text, transcript, or OCR is required for Quick Search",
                    "similar_frames": [],
                    "rows": []
                }

        # Create vector embedding from text
        vector = request.app.state.clip14_model.embed(text_query)

        similar_frames = []
        video_keyframes = {}

        # Decide search limit
        if ocr_query or transcript_query:
            search_limit = 2000
        else:
            search_limit = 500

        # Always run vector search
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 64}}
        results = request.app.state.milvus_keyframe.search(
            collection_name="keyframe_vectors",
            data=[vector.tolist()],
            anns_field="clip_feature_vector",
            search_params=search_params,
            limit=search_limit,
            output_fields=["video_name", "keyframe_path", "youtube_url", "ocr_text", "keyframe_index"]
        )

        # Flatten results to a list of dicts
        for hits in results:
            for hit in hits:
                video_name = hit.get("video_name")
                keyframe_path = hit.get("keyframe_path")
                youtube_url = hit.get("youtube_url")
                ocr_text = hit.get("ocr_text", "")
                keyframe = hit.get("keyframe_index")
                similarity_score = hit.score

                if mode == 1 and not video_name.startswith("L26_"):
                    continue
                if mode == 2 and not video_name.startswith("L25_"):
                    continue
                
                
                
                similar_frames.append({
                    "video_name": video_name,
                    "keyframe_path": keyframe_path,
                    "keyframe": keyframe,
                    "youtube_url": youtube_url,
                    "similarity_score": similarity_score
                })

                # Store OCR text and similarity score for later filtering
                if video_name not in video_keyframes:
                    video_keyframes[video_name] = []
                video_keyframes[video_name].append((keyframe_path, youtube_url, keyframe, ocr_text, similarity_score))

        rows = []
        for video_name, keyframe_items in video_keyframes.items():
            keyframe_items.sort(key=lambda x: int(x[2]))  # Sort by keyframe index
            keyframe_paths, youtube_links, keyframes, ocr_texts, similarity_scores = zip(
                *[(p, u, str(idx), (ocr or ""), sim_score) for p, u, idx, ocr, sim_score in keyframe_items]
            )

            # Use best similarity score from text search (highest = most relevant)
            best_similarity_score = max(similarity_scores)
            best_idx = max(range(len(similarity_scores)), key=lambda i: similarity_scores[i])

            rows.append({
                "video_name": video_name,
                "keyframe_paths": keyframe_paths,
                "keyframes": keyframes,
                "youtube_links": youtube_links,
                "ocr_text": ocr_texts,
                "similarity_score": best_similarity_score,  # From text vector search
                "keyframe_index": int(keyframes[best_idx]),   # New Field add
            })

        # Add transcript
        for r in rows:
            if "transcript" not in r or not r["transcript"]:
                r["transcript"] = get_transcript(r["video_name"], int(r["keyframes"][0])) or ""

        # Transcript filter: use exact match when transcript is provided
        if transcript_query:
            filtered = []

            for r in rows:
                # Use exact match for transcript filtering
                if exact_text_match(transcript_query, r["transcript"]):
                    # Also calculate fuzzy score for secondary ranking
                    fuzzy_score = is_text_match(transcript_query, r["transcript"])
                    r["transcript_score"] = fuzzy_score if fuzzy_score > 0 else 100  # Exact match = 100
                    filtered.append(r)

            rows = filtered
        else:
            # Set transcript_score to 0 if no transcript query
            for r in rows:
                r["transcript_score"] = 0

        # OCR filter: use fuzzy match (70-80% threshold) when OCR is provided
        if ocr_query:
            filtered = []

            for r in rows:
                # Check if any OCR text in the row matches
                ocr_texts = r.get("ocr_text", [])
                if not isinstance(ocr_texts, (list, tuple)):
                    ocr_texts = [ocr_texts] if ocr_texts else []
                
                matched = False
                best_ocr_score = 0
                
                for ocr_text in ocr_texts:
                    # Use fuzzy match with threshold 70
                    fuzzy_score = is_text_match(ocr_query, str(ocr_text), threshold=70)
                    if fuzzy_score >= 70:  # Accept if similarity >= 70%
                        matched = True
                        best_ocr_score = max(best_ocr_score, fuzzy_score)
                
                if matched:
                    r["ocr_score"] = best_ocr_score
                    filtered.append(r)

            rows = filtered
        else:
            # Set ocr_score to 0 if no OCR query
            for r in rows:
                r["ocr_score"] = 0

        # # Sort rows: prioritize similarity_score from text search, then transcript_score, then ocr_score
        # rows = sorted(rows, key=lambda x: (
        #     x.get("similarity_score", 0),  # Primary: text vector similarity (highest priority)
        #     x.get("transcript_score", 0),  # Secondary: transcript match score
        #     x.get("ocr_score", 0),         # Tertiary: OCR match score
        #     len(x.get("keyframes", []))    # Last: number of keyframes
        # ), reverse=True)

        # New Sort
        rows = rerank_candidates(
            rows,
            query_vector=vector,  
            milvus_keyframe_client=request.app.state.milvus_keyframe,
            has_transcript_query=bool(transcript_query),
            has_ocr_query=bool(ocr_query),
        )


        # # Fill each row
        # for row in rows:
        #     keyframe_paths = row["keyframe_paths"]
        #     keyframes = row["keyframes"]
        #     youtube_links = row["youtube_links"]
        #     video_name = row["video_name"]

        #     if len(keyframes) > 5:
        #         continue  # Skip if too many keyframes

        #     start = VIDEO_KEYFRAMES_MAP.get(video_name, []).index(keyframes[0])
        #     end = VIDEO_KEYFRAMES_MAP.get(video_name, []).index(keyframes[-1])

        #     if abs(end - start) < 10:
        #         start = max(0, start - 5)
        #         end = min(len(VIDEO_KEYFRAMES_MAP.get(video_name, [])), end + 5)

        #         keyframes = VIDEO_KEYFRAMES_MAP.get(video_name, [])[start:end]
        #         keyframe_paths = []
        #         youtube_links = []
        #         for k in keyframes:
        #             info = get_keyframe_info_from_db(k, request)
        #             if info:
        #                 keyframe_paths.append(info.get("keyframe_path"))
        #                 youtube_links.append(info.get("youtube_url"))
        #             else:
        #                 keyframe_paths.append(None)
        #                 youtube_links.append(None)

        #                 print("[WARNING] Keyframe info not found in DB:", video_name, k)

        #     # print(f"[INFO] Video {video_name} keyframes from {keyframes[0]} to {keyframes[-1]} (pos {start} to {end})")
        #     row["keyframes"] = keyframes
        #     row["keyframe_paths"] = keyframe_paths
        #     row["youtube_links"] = youtube_links

        return {
            "similar_frames": similar_frames,
            "rows": rows
        }

    except Exception as e:
        return {
            "error": f"Failed to process request: {str(e)}",
            "similar_frames": [],
            "rows": []
        }



# =====================
# Multi-keyframe Search (with text)
# =====================
class KeyframesInput(BaseModel):
    keyframe_paths: List[str]
    text: str = ""

@router.post("/multi-keyframe-search/")
async def multi_keyframe_search(input: KeyframesInput, request: Request):
    print(f"[REQUEST] /multi-keyframe-search/ received: {input.dict()}")
    try:
        keyframe_paths = input.keyframe_paths
        query_text = input.text.strip()

        if not keyframe_paths and not query_text:
            return {"error": "No keyframe paths or text provided", "similar_frames": [], "rows": []}

        vectors = []

        # If keyframe paths are provided, retrieve vectors from Milvus
        if keyframe_paths:
            results = request.app.state.milvus_keyframe.query(
                collection_name="keyframe_vectors",
                filter=f'keyframe_path in {keyframe_paths}',
                output_fields=["video_name", "keyframe_path", "clip_feature_vector", "youtube_url"]
            )

            if results:
                vectors.extend([np.array(item["clip_feature_vector"], dtype=np.float32) for item in results])

        # If text is provided, get embedding from CLIP
        text_vector = None
        if query_text:
            text_vector = request.app.state.clip14_model.embed(query_text)

        # If no vectors are found, return error
        if not vectors and text_vector is None:
            return {"error": "No valid vectors found", "similar_frames": [], "rows": []}

        # Compute average vector
        if text_vector is not None and vectors:
            # keyframes weight = 1, text weight = 2
            avg_vector = (np.mean(vectors, axis=0) * 1 + text_vector * 2) / 3
        elif text_vector is not None:
            avg_vector = text_vector
        else:
            avg_vector = np.mean(vectors, axis=0)

        # Perform search
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 64}}
        search_results = request.app.state.milvus_keyframe.search(
            collection_name="keyframe_vectors",
            data=[avg_vector.tolist()],
            anns_field="clip_feature_vector",
            search_params=search_params,
            limit=500,
            output_fields=["video_name", "keyframe_path", "youtube_url"]
        )

        # Process search results
        similar_frames = []
        video_keyframes = {}

        for hits in search_results:
            for hit in hits:
                video_name = hit.entity.get("video_name")
                keyframe_path = hit.entity.get("keyframe_path")
                youtube_url = hit.entity.get("youtube_url")
                keyframe = process_keyframe_path(keyframe_path)
                similarity_score = hit.score

                similar_frames.append({
                    "video_name": video_name,
                    "keyframe_path": keyframe_path,
                    "keyframe": keyframe,
                    "youtube_url": youtube_url,
                    "similarity_score": similarity_score
                })

                if video_name not in video_keyframes:
                    video_keyframes[video_name] = []
                video_keyframes[video_name].append((keyframe_path, youtube_url))

        # Sort keyframes by id
        def extract_keyframe_id(path):
            filename = path.split('/')[-1]
            match = re.search(r'\d+', filename)
            return int(match.group()) if match else 0

        rows = []
        for video_name, keyframe_items in video_keyframes.items():
            sorted_items = sorted(keyframe_items, key=lambda x: extract_keyframe_id(x[0]))
            sorted_keyframe_paths = [item[0] for item in sorted_items]
            youtube_links = [item[1] for item in sorted_items]
            keyframes = [process_keyframe_path(path) for path in sorted_keyframe_paths]

            if len(keyframes) > 0:
                transcript = get_transcript(video_name, int(keyframes[0])) or ""

            rows.append({
                "video_name": video_name,
                "keyframe_paths": sorted_keyframe_paths,
                "keyframes": keyframes,
                "youtube_links": youtube_links,
                "transcript": transcript
            })

        return {
            "similar_frames": similar_frames,
            "rows": rows
        }

    except Exception as e:
        return {
            "error": f"Failed to process request: {str(e)}",
            "similar_frames": [],
            "rows": []
        }



# =====================
# Context Sequence
# =====================
class SingleKeyframeInput(BaseModel):
    keyframe_path: str

@router.post("/context-sequence/")
async def context_sequence(input: SingleKeyframeInput, request: Request):
    try:
        print(f"[REQUEST] /context-sequence/ received: {input.dict()}")
        keyframe_path = input.keyframe_path

        # Query the original keyframe from Milvus
        results = request.app.state.milvus_keyframe.query(
            collection_name="keyframe_vectors",
            filter=f'keyframe_path == "{keyframe_path}"',
            output_fields=["video_name", "keyframe_index", "keyframe_path", "youtube_url"]
        )

        if not results:
            return {"error": f"Keyframe {keyframe_path} not found", "frames": []}

        keyframe_info = results[0]
        video_name = keyframe_info["video_name"]
        current_index = int(keyframe_info["keyframe_index"])

        # Get all keyframes of the same video
        all_keyframes = request.app.state.milvus_keyframe.query(
            collection_name="keyframe_vectors",
            filter=f'video_name == "{video_name}"',
            output_fields=["keyframe_index", "keyframe_path", "youtube_url"]
        )

        if not all_keyframes:
            return {"error": f"No keyframes found for video {video_name}", "frames": []}

        # Sort by keyframe_index
        sorted_keyframes = sorted(
            all_keyframes,
            key=lambda x: int(x["keyframe_index"])
        )

        # Find the index position in the list
        pos = next((i for i, k in enumerate(sorted_keyframes) if k["keyframe_path"] == keyframe_path), None)
        if pos is None:
            return {"error": "Keyframe not found in its own video list", "frames": []}

        # Get 10 before and 10 after
        start = max(0, pos - 10)
        end = min(len(sorted_keyframes), pos + 11)

        selected_frames = sorted_keyframes[start:end]

        # Format output (video_name is not included inside)
        frames = [
            {
                "keyframe_path": frame["keyframe_path"],
                "youtube_url": frame["youtube_url"]
            }
            for frame in selected_frames
        ]

        return {
            "video_name": video_name,
            "frames": frames
        }

    except Exception as e:
        return {
            "error": f"Failed to process request: {str(e)}",
            "frames": []
        }