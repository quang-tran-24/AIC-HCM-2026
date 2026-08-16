"""
Offline CLI for the Q&A pipeline — no FastAPI server required.

`context` and `question` are passed in directly (matching the web UI's two separate
fields — see backend/qa_answer.py's module docstring for why there's no more auto-split
of a single blob of text).

Usage (run from repo root, inside .venv-wsl):

    # single query, print result only
    python3 -m tools.qa_cli \\
        --context "Đoạn video về một người phụ nữ dạy nấu ăn, cầm công thức món ăn với nguyên liệu chính là 200g thịt nạc xay." \\
        --question "Tiêu đề của công thức nấu ăn (tên món ăn) này là gì?"

    # same, but reading each field from a plain text file instead of a shell arg
    python3 -m tools.qa_cli --context-file ctx.txt --question-file q.txt

    # single query, write submission/<name>.csv in "video_id,frame_id,answer" format
    python3 -m tools.qa_cli --context "..." --question "..." --name query-p1-15-qa --write-csv

    # batch mode: JSON list of {"name": ..., "context": ..., "question": ...} objects
    python3 -m tools.qa_cli --batch-json queries.json --write-csv

    # feed 3 frames (located frame + 2 positional neighbors) to Qwen instead of just 1
    python3 -m tools.qa_cli --context "..." --question "..." --context-frames 3

First run downloads Qwen2.5-VL-3B-Instruct from the Hugging Face Hub (a few GB) — make
sure the machine has internet access and enough disk space before running.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymilvus import MilvusClient

from backend.clip_vit_large_14_model import CLIP_ViT_L_14
from backend.vietnamese_to_english_translator import VietnameseToEnglishTranslator
from backend.qa_answer import run_qa_query, QwenVLAnswerer

KEYFRAME_DB_PATH = os.path.join("databases", "keyframe_vectors.db")
FPS_JSON_FILE = os.path.join("datasets", "fps.json")
SUBMISSION_DIR = "submission"


def load_context(quantize: bool = True):
    print("[INFO] Loading CLIP model...")
    clip_model = CLIP_ViT_L_14()

    print("[INFO] Loading Vietnamese->English translator...")
    translator = VietnameseToEnglishTranslator()

    print(f"[INFO] Connecting to keyframe_vectors at {KEYFRAME_DB_PATH}...")
    milvus_keyframe = MilvusClient(uri=KEYFRAME_DB_PATH)
    milvus_keyframe.load_collection("keyframe_vectors")

    with open(FPS_JSON_FILE, "r", encoding="utf-8") as f:
        fps_dict = json.load(f)

    qwen_answerer = QwenVLAnswerer(quantize=quantize)

    return clip_model, translator, milvus_keyframe, fps_dict, qwen_answerer


def run_one(name, context, question, clip_model, translator, milvus_keyframe, fps_dict,
            qwen_answerer, num_context_frames=1, write_csv=False):
    t0 = time.time()
    result = run_qa_query(
        context_vi=context,
        question_vi=question,
        milvus_keyframe_client=milvus_keyframe,
        clip_model=clip_model,
        translator=translator,
        qwen_answerer=qwen_answerer,
        fps_dict=fps_dict,
        num_context_frames=num_context_frames,
    )
    elapsed = time.time() - t0

    csv_row = f"{result['video_name']},{result['frame_id']},{result['answer']}"

    print(f"\n=== {name} ({elapsed:.1f}s) ===")
    print(f"  context  : {result['context_vi']}")
    print(f"  question : {result['question_vi']}")
    print(f"  video_name / frame_id : {result['video_name']} / {result['frame_id']}")
    print(f"  answer   : {result['answer']}")
    print(f"  csv_row  : {csv_row}")

    if write_csv:
        os.makedirs(SUBMISSION_DIR, exist_ok=True)
        out_path = os.path.join(SUBMISSION_DIR, f"{name}.csv")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(csv_row + "\n")
        print(f"  -> wrote {out_path}")

    return result


def _read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def main():
    parser = argparse.ArgumentParser(description="Run the Q&A pipeline offline.")
    parser.add_argument("--context", help="Context/description text (mô tả sự kiện)")
    parser.add_argument("--question", help="Question text (câu hỏi)")
    parser.add_argument("--context-file", help="Path to a text file containing the context, instead of --context")
    parser.add_argument("--question-file", help="Path to a text file containing the question, instead of --question")
    parser.add_argument("--name", default="qa-query", help="Name used for the output CSV file (submission/<name>.csv)")
    parser.add_argument("--batch-json", help="Path to a JSON file: list of {name, context, question} objects (batch mode)")
    parser.add_argument("--context-frames", type=int, default=1, help="Number of neighboring frames to feed Qwen (default 1 = just the located frame)")
    parser.add_argument("--no-quantize", action="store_true", help="Load Qwen in fp16 instead of 4-bit (needs more VRAM)")
    parser.add_argument("--write-csv", action="store_true", help="Write result(s) to submission/<name>.csv")
    args = parser.parse_args()

    if args.batch_json:
        with open(args.batch_json, "r", encoding="utf-8") as f:
            queries = json.load(f)
    else:
        context = args.context or (_read_file(args.context_file) if args.context_file else None)
        question = args.question or (_read_file(args.question_file) if args.question_file else None)
        if not context or not question:
            parser.error("Provide both context and question (via --context/--question, --context-file/--question-file, or --batch-json)")
        queries = [{"name": args.name, "context": context, "question": question}]

    clip_model, translator, milvus_keyframe, fps_dict, qwen_answerer = load_context(quantize=not args.no_quantize)

    for q in queries:
        try:
            run_one(
                q["name"], q["context"], q["question"],
                clip_model, translator, milvus_keyframe, fps_dict, qwen_answerer,
                num_context_frames=args.context_frames, write_csv=args.write_csv,
            )
        except Exception as e:
            print(f"[ERROR] {q.get('name', '?')}: {e}")


if __name__ == "__main__":
    main()