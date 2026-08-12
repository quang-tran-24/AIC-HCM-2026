"""
Q&A module (query dạng 2 — Textual Question Answering).

Pipeline per AIC-HCMC 2026 rules section 1.2:
  1. Retrieval: embed `context` with CLIP, search+rerank keyframe_vectors (reusing
     backend/rerank.py's rerank_candidates so both search endpoints stay consistent),
     take the best-scoring frame.
  2. Answer: build a prompt for a local Qwen2.5-VL from the located frame's image + any
     OCR text already extracted for it + nearby transcript text, and ask the question.

`context` and `question` are passed in as two separate fields, not parsed out of one blob
of text. Earlier versions of this module tried to auto-detect the question boundary within
a single pasted block (BTC's query-*-qa.txt files are one continuous paragraph). Now that
the frontend has a dedicated Q&A tab, the person searching already knows they're answering
a question and can just type the context and the question into two separate boxes — so
guessing where one ends and the other begins in a merged string is unnecessary complexity
and a real (if rare) failure mode. This module now just takes both directly.

Why OCR/transcript context matters here specifically: real query-*-qa.txt examples are
dominated by "read the text in the frame" questions (a commune name on a sign, a dish
name on a recipe card, verses carved on a wall) rather than generic visual questions. A
VLM's own in-image OCR on a possibly low-res keyframe is less reliable than the OCR
already extracted for that frame — so it's supplied as text context alongside the image
rather than relied on alone.
"""

import json
import os
from typing import List, Optional

from PIL import Image

from backend.rerank import rerank_candidates

DATASETS_DIR = "datasets"
TRANSCRIPT_DIR = os.path.join(DATASETS_DIR, "transcripts")


# ---------------------------------------------------------------------------
# Stage 1: retrieval (reuses backend/rerank.py, same fusion as quick_search.py)
# ---------------------------------------------------------------------------

def retrieve_best_frame(
    context_text_en: str,
    milvus_keyframe_client,
    clip_model,
    top_k: int = 100,
) -> Optional[dict]:
    """CLIP search + weighted rerank (no OCR/transcript query terms -- a QA context isn't
    a literal OCR/transcript string to match) over keyframe_vectors, returns the top hit
    as a dict with video_name / keyframe_index / keyframe_path / ocr_text / final_score."""
    vector = clip_model.embed(context_text_en)

    search_params = {"metric_type": "COSINE", "params": {"nprobe": 64}}
    results = milvus_keyframe_client.search(
        collection_name="keyframe_vectors",
        data=[vector.tolist()],
        anns_field="clip_feature_vector",
        search_params=search_params,
        limit=top_k,
        output_fields=["video_name", "keyframe_path", "keyframe_index", "ocr_text"],
    )

    candidates = []
    for hits in results:
        for hit in hits:
            try:
                keyframe_index = int(hit.get("keyframe_index"))
            except (TypeError, ValueError):
                continue
            candidates.append({
                "video_name": hit.get("video_name"),
                "keyframe_path": hit.get("keyframe_path"),
                "keyframe_index": keyframe_index,
                "ocr_text": hit.get("ocr_text", ""),
                "ocr_score": 0,
                "transcript_score": 0,
                "similarity_score": hit.score,
            })

    if not candidates:
        return None

    reranked = rerank_candidates(
        candidates,
        query_vector=vector,
        milvus_keyframe_client=milvus_keyframe_client,
        has_transcript_query=False,
        has_ocr_query=False,
    )
    return reranked[0]


# ---------------------------------------------------------------------------
# Context assembly: transcript + neighboring frame images
# ---------------------------------------------------------------------------

def get_transcript_context(video_name: str, frame_id: int, fps_dict: dict) -> str:
    """Transcript text around frame_id's timestamp (prev/current/next 10s bucket), same
    bucketing convention as quick_search.py's get_transcript(), kept self-contained here
    to avoid importing quick_search.py's module-level side effects (it reads whole
    directories into memory at import time)."""
    fps = fps_dict.get(video_name)
    if not fps:
        return ""

    path = os.path.join(TRANSCRIPT_DIR, f"{video_name}.json")
    if not os.path.exists(path):
        return ""

    try:
        with open(path, "r", encoding="utf-8") as f:
            segments = json.load(f)
    except Exception:
        return ""

    seconds = frame_id / fps
    idx = int(seconds // 10)

    parts = []
    for i in (idx - 1, idx, idx + 1):
        if 0 <= i < len(segments):
            t = segments[i].get("transcript", "")
            if t:
                parts.append(t)
    return " ".join(parts).strip()


def get_context_frame_paths(
    video_name: str,
    frame_id: int,
    milvus_keyframe_client,
    num_context_frames: int = 1,
) -> Optional[List[str]]:
    """Positionally-adjacent keyframe paths (not frame-distance neighbors, same rationale
    as backend/rerank.py's neighbor scoring: TransNetV2 keyframes are spaced irregularly).
    Returns None if num_context_frames <= 1 (caller should just use the primary frame)."""
    if num_context_frames <= 1:
        return None

    results = milvus_keyframe_client.query(
        collection_name="keyframe_vectors",
        filter=f'video_name == "{video_name}"',
        output_fields=["keyframe_index", "keyframe_path"],
    )
    pairs = sorted(
        ((int(r["keyframe_index"]), r["keyframe_path"]) for r in results or []),
        key=lambda p: p[0],
    )
    pos = next((i for i, (idx, _) in enumerate(pairs) if idx == frame_id), None)
    if pos is None:
        return None

    half = (num_context_frames - 1) // 2
    lo = max(0, pos - half)
    hi = min(len(pairs), lo + num_context_frames)
    lo = max(0, hi - num_context_frames)
    return [p for _, p in pairs[lo:hi]]


# ---------------------------------------------------------------------------
# Stage 2: Qwen2.5-VL answering
# ---------------------------------------------------------------------------

QWEN_MODEL_NAME = "Qwen/Qwen2.5-VL-3B-Instruct"


class QwenVLAnswerer:
    """
    Local Qwen2.5-VL wrapper, 4-bit quantized by default. 3B (not 7B) is the deliberate
    choice here: on a 6GB VRAM card already holding CLIP, 7B in 4-bit alone is close to
    the VRAM ceiling and leaves no room to run alongside CLIP without unloading it every
    search. 3B in 4-bit is small enough to coexist.

    NOTE: model loading and .generate() need an actual GPU + a Hugging Face Hub download,
    neither of which is available in the sandbox this code was written in -- the rest of
    this module's logic was tested end-to-end against a mocked Milvus client, but this
    class's actual inference path needs to be verified on your machine. If the
    transformers API for Qwen2.5-VL has moved since this was written, check the model
    card on the Hub for the current usage snippet.
    """

    def __init__(self, model_name: str = QWEN_MODEL_NAME, quantize: bool = True, device: str = "cuda"):
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        self.device = device
        quant_config = None
        if quantize:
            from transformers import BitsAndBytesConfig
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )

        print(f"[INFO] Loading {model_name} (quantize={quantize})...")
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            quantization_config=quant_config,
            device_map=device,
        )
        self.processor = AutoProcessor.from_pretrained(model_name)
        print("[INFO] Qwen2.5-VL loaded.")

    def _build_prompt(self, question: str, ocr_context: str, transcript_context: str) -> str:
        parts = []
        if ocr_context:
            parts.append(f"Văn bản OCR nhận dạng được trong khung hình (có thể có lỗi nhận dạng ký tự): {ocr_context}")
        if transcript_context:
            parts.append(f"Lời thoại/phụ đề gần thời điểm này: {transcript_context}")
        parts.append(f"Câu hỏi: {question}")
        parts.append("Trả lời ngắn gọn và trực tiếp nhất có thể (chỉ tên/số/cụm từ ngắn), không giải thích thêm.")
        return "\n".join(parts)

    def answer(
        self,
        images: List[Image.Image],
        question: str,
        ocr_context: str = "",
        transcript_context: str = "",
        max_new_tokens: int = 64,
    ) -> str:
        from qwen_vl_utils import process_vision_info

        content = [{"type": "image", "image": img} for img in images]
        content.append({"type": "text", "text": self._build_prompt(question, ocr_context, transcript_context)})
        messages = [{"role": "user", "content": content}]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text], images=image_inputs, videos=video_inputs,
            padding=True, return_tensors="pt",
        ).to(self.device)

        import torch
        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
        output_text = self.processor.batch_decode(
            trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False,
        )
        return output_text[0].strip()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_qa_query(
    context_vi: str,
    question_vi: str,
    milvus_keyframe_client,
    clip_model,
    translator,
    qwen_answerer: QwenVLAnswerer,
    fps_dict: dict,
    num_context_frames: int = 1,
    top_k: int = 100,
) -> dict:
    context_vi = (context_vi or "").strip()
    question_vi = (question_vi or "").strip()
    if not context_vi:
        raise ValueError("Context (mô tả sự kiện) không được để trống")
    if not question_vi:
        raise ValueError("Question (câu hỏi) không được để trống")

    context_en = translator.translate(context_vi)
    best = retrieve_best_frame(context_en, milvus_keyframe_client, clip_model, top_k=top_k)
    if best is None:
        raise RuntimeError("No candidate frame found for this QA query")

    video_name = best["video_name"]
    frame_id = best["keyframe_index"]

    frame_paths = get_context_frame_paths(video_name, frame_id, milvus_keyframe_client, num_context_frames)
    if not frame_paths:
        frame_paths = [best["keyframe_path"]]

    images = []
    for p in frame_paths:
        try:
            images.append(Image.open(p).convert("RGB"))
        except Exception as e:
            print(f"[WARN] qa_answer: failed to load image {p}: {e}")

    if not images:
        raise RuntimeError(f"Could not load any candidate image for {video_name} frame {frame_id} (path: {frame_paths})")

    ocr_context = best.get("ocr_text") or ""
    if isinstance(ocr_context, (list, tuple)):
        ocr_context = " ".join(str(t) for t in ocr_context if t)

    transcript_context = get_transcript_context(video_name, frame_id, fps_dict)

    # Ask in the original Vietnamese -- rules explicitly allow a Vietnamese or English
    # answer, and Qwen2.5-VL is multilingual; keeping it native avoids compounding
    # translation error on what's usually a short factual answer (a name, a number).
    answer = qwen_answerer.answer(
        images=images,
        question=question_vi,
        ocr_context=ocr_context,
        transcript_context=transcript_context,
    )

    return {
        "video_name": video_name,
        "frame_id": frame_id,
        "keyframe_path": best["keyframe_path"],  # real stored path (correct padding/ext) for UI display
        "answer": answer,
        "context_vi": context_vi,
        "question_vi": question_vi,
        "retrieval_score": best.get("final_score", best.get("similarity_score")),
    }