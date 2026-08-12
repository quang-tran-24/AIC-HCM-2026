import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.qa_answer import run_qa_query

router = APIRouter()


class QAInput(BaseModel):
    context: str              # mô tả sự kiện (dùng để định vị video/frame qua CLIP)
    question: str             # câu hỏi (đưa thẳng cho Qwen2.5-VL, không cần đoán từ context)
    num_context_frames: int = 1  # 1 = chỉ frame định vị được; 3/5 = kèm frame lân cận


@router.post("/qa-search/")
async def qa_search(input: QAInput, request: Request):
    print(f"[REQUEST] /qa-search/ received: {input.dict()}")
    try:
        # run_qa_query is synchronous (CLIP embed, Milvus query, and — the slow part —
        # Qwen2.5-VL .generate(), all blocking calls). Calling it directly here would
        # block uvicorn's single asyncio event loop for the whole duration, stalling
        # every other in-flight request (including /quick-search/ and /trake-search/)
        # until this one finishes. asyncio.to_thread runs it in a worker thread instead,
        # so a slow Q&A answer no longer holds up unrelated KIS/TRAKE searches.
        result = await asyncio.to_thread(
            run_qa_query,
            context_vi=input.context,
            question_vi=input.question,
            milvus_keyframe_client=request.app.state.milvus_keyframe,
            clip_model=request.app.state.clip14_model,
            translator=request.app.state.vi_to_en_translator,
            qwen_answerer=request.app.state.qwen_vl_answerer,
            fps_dict=request.app.state.fps_dict,
            num_context_frames=input.num_context_frames,
        )

        csv_row = f"{result['video_name']},{result['frame_id']},{result['answer']}"

        return {
            "video_name": result["video_name"],
            "frame_id": result["frame_id"],
            "keyframe_path": result["keyframe_path"],
            "answer": result["answer"],
            "csv_row": csv_row,
            "context_vi": result["context_vi"],
            "question_vi": result["question_vi"],
            "retrieval_score": result["retrieval_score"],
        }

    except Exception as e:
        return {"error": f"Failed to process QA request: {str(e)}"}