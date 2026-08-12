"""
Debug script: chạy thử pipeline transcript MỚI (cắt thủ công từng đoạn 10s, không dùng
chunk_length_s/return_timestamps) trên vài bucket đầu của 1 video, in kết quả ra ngay --
không cần đợi hết cả video như batch chính.

Cách chạy (từ repo root):
    python3 data_processing/debug_transcript.py datasets/videos/batch_1/L21_V001.mp4
    python3 data_processing/debug_transcript.py datasets/videos/batch_1/L21_V001.mp4 --buckets 6
"""

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from transcript_extraction import extract_audio_clip, get_duration_seconds, load_asr_pipeline, BUCKET_SECONDS

parser = argparse.ArgumentParser()
parser.add_argument("video_path")
parser.add_argument("--buckets", type=int, default=6, help="Số bucket 10s đầu để thử (mặc định 6 = 1 phút)")
args = parser.parse_args()

duration = get_duration_seconds(args.video_path)
print(f"Video duration: {duration:.1f}s")

asr = load_asr_pipeline()

with tempfile.TemporaryDirectory() as tmp_dir:
    num_buckets = min(args.buckets, int(duration // BUCKET_SECONDS) + 1)
    for i in range(num_buckets):
        start_sec = i * BUCKET_SECONDS
        clip_duration = min(BUCKET_SECONDS, duration - start_sec)
        clip_path = os.path.join(tmp_dir, f"clip_{i:05d}.wav")

        extract_audio_clip(args.video_path, start_sec, clip_duration, clip_path)
        result = asr(clip_path)
        text = (result.get("text") or "").strip()

        print(f"\n=== Bucket {i} ({start_sec}s - {start_sec + clip_duration:.0f}s) ===")
        print(repr(text) if text else "(rỗng -- không có tiếng nói trong đoạn này, hoặc lỗi)")

        os.remove(clip_path)

print(f"\n[INFO] Xong {num_buckets} bucket thử nghiệm. Nếu thấy chữ tiếng Việt hợp lý ở "
      f"phần lớn bucket, chạy full batch: python3 data_processing/transcript_extraction.py")