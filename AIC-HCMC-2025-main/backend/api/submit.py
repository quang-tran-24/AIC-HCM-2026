from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
import json
import requests
import os

# =====================
# DRES API configuration
# =====================
DRES_URL = "https://eventretrieval.oj.io.vn/api/v2"
USERNAME = "team023"
PASSWORD = "CYAYWjxzSh"
EVAL_INDEX = 0

# Global session info
SESSION_ID = None
EVALUATION_ID = None

# =====================
# FPS data
# =====================
fps_json_file = os.path.join("datasets", "fps.json")
with open(fps_json_file, "r") as f:
    FPS_DATA = json.load(f)

router = APIRouter()

# =====================
# Pydantic models
# =====================
class FrameItem(BaseModel):
    video_name: str
    keyframe_idx: float

class SubmitRequest(BaseModel):
    mode: int                   # 1 = KIS, 2 = QA, 3 = TRAKE
    selected_frames: List[FrameItem]
    answer: str


# =====================
# Helper functions
# =====================
def dres_login():
    """Step 1: Login to DRES and store sessionId"""
    global SESSION_ID
    if SESSION_ID is not None:
        return SESSION_ID

    print("[INFO] Logging in to DRES...")
    resp = requests.post(f"{DRES_URL}/login", json={"username": USERNAME, "password": PASSWORD})
    resp.raise_for_status()
    SESSION_ID = resp.json().get("sessionId")
    print(f"[INFO] Got sessionId: {SESSION_ID}")
    return SESSION_ID


def get_evaluation_id():
    """Step 2: Get active evaluation ID (with optional index selection)"""
    global EVALUATION_ID
    if EVALUATION_ID is not None:
        return EVALUATION_ID

    session = dres_login()
    print("[INFO] Fetching evaluation list...")
    resp = requests.get(f"{DRES_URL}/client/evaluation/list", params={"session": session})
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list) or len(data) == 0:
        raise RuntimeError("No evaluations found in DRES response.")

    print(f"[INFO] Received {len(data)} evaluations:")
    for i, ev in enumerate(data):
        print(f"  [{i}] id={ev.get('id')} status={ev.get('status')}")

    # Chọn ID theo index
    try:
        chosen_eval = data[EVAL_INDEX]
    except IndexError:
        raise IndexError(f"EVAL_INDEX={EVAL_INDEX} is out of range (max index = {len(data)-1})")

    EVALUATION_ID = chosen_eval["id"]
    print(f"[INFO] Using evaluationID at index {EVAL_INDEX}: {EVALUATION_ID}")
    return EVALUATION_ID


def frame_to_ms(video_name: str, frame_idx: int) -> int:
    """Convert frame index to milliseconds using FPS_DATA"""
    fps = FPS_DATA.get(video_name)
    if not fps or fps <= 0:
        raise ValueError(f"Missing or invalid FPS for video {video_name}")
    return int((frame_idx / fps) * 1000)


def submit_to_dres(answer_body: dict):
    """Step 3: Submit answer to DRES"""
    session = dres_login()
    eval_id = get_evaluation_id()

    submit_url = f"{DRES_URL}/submit/{eval_id}?session={session}"
    print(f"[INFO] Submitting to {submit_url}")
    print(f"[INFO] Body: {json.dumps(answer_body, ensure_ascii=False)}")

    resp = requests.post(submit_url, json=answer_body)
    print(f"[INFO] Raw response ({resp.status_code}): {resp.text}")

    # Print out into console
    try:
        data = resp.json()
        print("=== DRES RESPONSE ===")
        print(f"Status: {data.get('status')}")
        print(f"Submission: {data.get('submission')}")
        print(f"Description: {data.get('description')}")
        print("=====================")
    except Exception:
        print("[WARN] Response is not valid JSON, cannot parse DRES result")

    resp.raise_for_status()
    return resp.json()

# =====================
# API route
# =====================
@router.post("/submit/")
async def submit_data(payload: SubmitRequest):
    print("=== /submit/ received payload ===")
    print(json.dumps(payload.model_dump(), ensure_ascii=False, indent=2))
    print("================================")

    try:
        if not payload.selected_frames:
            raise ValueError("selected_frames cannot be empty.")

        # Always use the earliest frame
        first_frame = payload.selected_frames[0]
        video_name = first_frame.video_name
        frame_idx = first_frame.keyframe_idx

        # Convert frame index to ms (for KIS/QA)
        timestamp_ms = frame_to_ms(video_name, frame_idx)

        # Build body according to mode
        if payload.mode == 1:
            # Textual KIS / Video KIS
            body = {
                "answerSets": [{
                    "answers": [{
                        "mediaItemName": video_name,
                        "start": f"{timestamp_ms}",
                        "end": f"{timestamp_ms}"
                    }]
                }]
            }

        elif payload.mode == 2:
            # Question Answering
            body = {
                "answerSets": [{
                    "answers": [{
                        "text": f"QA-{payload.answer}-{video_name}-{timestamp_ms}"
                    }]
                }]
            }

        elif payload.mode == 3:
            # TRAKE: keyframe_idx thực chất là số giây (có thể là số thực).
            # Chuyển ngược sang frame_id bằng cách nhân với FPS của video và làm tròn.
            fps = FPS_DATA.get(video_name)
            if not fps or fps <= 0:
                raise ValueError(f"Missing or invalid FPS for video {video_name}")

            frame_ids = []
            for item in payload.selected_frames:
                try:
                    secs = float(item.keyframe_idx)
                except Exception:
                    raise ValueError(f"Invalid keyframe_idx value: {item.keyframe_idx}")
                frame_id = int(round(secs * fps))
                frame_ids.append(frame_id)

            body = {
                "answerSets": [{
                    "answers": [{
                        "text": f"TR-{video_name}-" + ",".join(map(str, frame_ids))
                    }]
                }]
            }
        else:
            raise ValueError(f"Unsupported mode: {payload.mode}")

        # Submit to DRES
        result = submit_to_dres(body)

        print("[INFO] Submission successful.")

        return {
            "success": True,
            "message": "Submission successful",
            "evaluation_id": EVALUATION_ID,
            "session_id": SESSION_ID,
            "result": result
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {
            "success": False,
            "message": str(e)
        }
