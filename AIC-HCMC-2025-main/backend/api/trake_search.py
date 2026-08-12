import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

from backend.trake_alignment import run_trake_query

router = APIRouter()


class TrakeInput(BaseModel):
    query_text: str                    # raw contents of a query-*-trake.txt file (context + "E1: ..." lines)
    forced_video_name: Optional[str] = None  # dev/debug only: skip stage-1, refine on a known video
    include_context: bool = True


@router.post("/trake-search/")
async def trake_search(input: TrakeInput, request: Request):
    print(f"[REQUEST] /trake-search/ received: {input.dict()}")

    if request.app.state.milvus_scene is None:
        return {
            "error": "scene_vectors chưa sẵn sàng — chạy 'python3 backend/load_scene_vector_database.py' "
                     "(tắt server trước) rồi khởi động lại backend."
        }

    try:
        # Same reasoning as qa_search.py: run_trake_query is synchronous (Milvus queries,
        # multiple ffmpeg subprocess calls, CLIP batch encode) — run it off the event loop
        # so a slow TRAKE query doesn't stall concurrent /quick-search/ or /qa-search/ calls.
        result = await asyncio.to_thread(
            run_trake_query,
            query_text=input.query_text,
            milvus_scene_client=request.app.state.milvus_scene,
            clip_model=request.app.state.clip14_model,
            translator=request.app.state.vi_to_en_translator,
            fps_dict=request.app.state.fps_dict,
            include_context=input.include_context,
            forced_video_name=input.forced_video_name,
        )

        csv_row = ",".join([result["video_name"]] + [str(f) for f in result["frame_ids"]])

        return {
            "video_name": result["video_name"],
            "frame_ids": result["frame_ids"],
            "frame_paths": result["frame_paths"],
            "csv_row": csv_row,
            "coarse_score": result["coarse_score"],
            "num_events": result["num_events"],
            "event_texts_vi": result["event_texts_vi"],
            "event_texts_en": result["event_texts_en"],
        }

    except Exception as e:
        return {"error": f"Failed to process TRAKE request: {str(e)}"}