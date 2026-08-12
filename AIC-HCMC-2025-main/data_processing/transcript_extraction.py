"""
Trích transcript (audio -> text) bằng PhoWhisper, bucket theo cửa sổ 10 giây đúng định
dạng mà backend/api/quick_search.py's get_transcript() và backend/qa_answer.py's
get_transcript_context() đã đọc sẵn -- datasets/transcripts/<video_name>.json =
[{"transcript": "..."}, ...] một phần tử mỗi bucket 10s, phủ hết thời lượng video (bucket
không có tiếng nói để rỗng "").

THIẾT KẾ (đã đổi sau khi debug thực tế): KHÔNG dùng chunk_length_s/return_timestamps của
pipeline nữa -- đã xác nhận bằng debug_transcript.py rằng với audio dài (~21 phút),
pipeline gộp toàn bộ thành 1 chunk với timestamp (None, None), khiến mọi transcript thật
bị loại bỏ dù model nghe đúng 100%. Đây là hành vi biết trước của transformers với audio
dài + chunk_length_s (chính transformers cũng cảnh báo "very experimental with seq2seq
models"), không phải lỗi do PhoWhisper hay ffmpeg.

Thay vào đó: tự cắt audio thành từng đoạn đúng 10 giây bằng ffmpeg (biết chính xác mốc
thời gian vì tự cắt, không cần suy luận từ timestamp model trả về), gọi ASR riêng cho
từng đoạn ngắn -- mỗi đoạn nằm gọn trong cửa sổ xử lý gốc 30s của Whisper nên không cần
cơ chế chia-chunk-nội-bộ phức tạp/không ổn định nữa.

Cách chạy:
    python3 data_processing/transcript_extraction.py
"""

import json
import os
import subprocess
import tempfile
from glob import glob

DATASETS_DIR = "datasets"
VIDEOS_DIR = os.path.join(DATASETS_DIR, "videos")
TRANSCRIPT_DIR = os.path.join(DATASETS_DIR, "transcripts")

BUCKET_SECONDS = 10  # PHẢI giữ = 10 -- get_transcript()/get_transcript_context() hardcode "seconds // 10"
ASR_MODEL_NAME = "vinai/PhoWhisper-medium"


def load_asr_pipeline():
    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    print(f"[INFO] Loading {ASR_MODEL_NAME} (device={'cuda' if device == 0 else 'cpu'})...")
    asr = pipeline(
        "automatic-speech-recognition",
        model=ASR_MODEL_NAME,
        device=device,
        generate_kwargs={"language": "vietnamese", "task": "transcribe"},
    )
    print("[INFO] ASR model loaded.")
    return asr


def get_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def extract_audio_clip(video_path: str, start_sec: float, duration_sec: float, out_wav: str):
    """Cắt trực tiếp 1 đoạn audio ngắn từ video gốc -- không cần -copyts/frame-accurate
    (khác dense_resample.py cho video): lệch vài trăm ms giữa các bucket transcript không
    quan trọng, vì get_transcript() đã tự cộng gộp bucket trước/sau khi tra cứu."""
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start_sec), "-t", str(duration_sec), "-i", video_path,
         "-vn", "-ac", "1", "-ar", "16000", out_wav],
        check=True, capture_output=True,
    )


def transcribe_video(video_path: str, asr, tmp_dir: str) -> list:
    duration = get_duration_seconds(video_path)
    num_buckets = int(duration // BUCKET_SECONDS) + 1
    buckets = [{"transcript": ""} for _ in range(num_buckets)]

    for i in range(num_buckets):
        start_sec = i * BUCKET_SECONDS
        clip_duration = min(BUCKET_SECONDS, duration - start_sec)
        if clip_duration < 0.5:  # đoạn đuôi quá ngắn, bỏ qua thay vì gọi ASR vô ích
            continue

        clip_path = os.path.join(tmp_dir, f"clip_{i:05d}.wav")
        try:
            extract_audio_clip(video_path, start_sec, clip_duration, clip_path)
            result = asr(clip_path)
            text = (result.get("text") or "").strip()
            buckets[i]["transcript"] = text
        except Exception as e:
            print(f"[WARN]   bucket {i} ({start_sec:.0f}s): {e}")
        finally:
            if os.path.exists(clip_path):
                os.remove(clip_path)

    return buckets


def main():
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    asr = load_asr_pipeline()

    video_paths = sorted(glob(os.path.join(VIDEOS_DIR, "*", "*.mp4")))
    print(f"[INFO] Found {len(video_paths)} videos")

    done, skipped = 0, 0
    with tempfile.TemporaryDirectory(prefix="transcript_clips_") as tmp_dir:
        for video_path in video_paths:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            out_json = os.path.join(TRANSCRIPT_DIR, f"{video_name}.json")

            if os.path.exists(out_json):
                skipped += 1
                continue

            print(f"[INFO] Transcribing {video_name}...")
            buckets = transcribe_video(video_path, asr, tmp_dir)

            non_empty = sum(1 for b in buckets if b["transcript"])
            print(f"[INFO]   {non_empty}/{len(buckets)} bucket có transcript")

            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(buckets, f, ensure_ascii=False, indent=2)

            done += 1

    print(f"[INFO] Done. Transcribed {done} videos, skipped {skipped} already present.")


if __name__ == "__main__":
    main()