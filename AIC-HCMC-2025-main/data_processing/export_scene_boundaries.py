"""
One-off catch-up script: tính lại scene boundary bằng TransNetV2 cho các video ĐÃ qua
pipeline chính (đã có keyframe + CLIP feature), và ghi ra đúng định dạng .scenes.txt mà
backend/load_scene_vector_database.py cần.

Vì sao cần file này: data_processing/main.py tính `frame_ranges` (ranh giới scene) qua
TransNetV2 chỉ để chọn frame nào lưu làm keyframe, rồi bỏ luôn `frame_ranges` chứ không
ghi ra đâu cả -- nên chưa từng có file nguồn cho dữ liệu cấp-scene mà TRAKE cần. Script
này chạy LẠI CHỈ riêng phần TransNetV2 (rẻ hơn nhiều so với chạy lại cả pipeline -- không
trích keyframe, không encode CLIP, không ghi PNG) để khôi phục và lưu lại ranh giới đó.

Với các video xử lý TỪ GIỜ VỀ SAU, thêm đoạn code đánh dấu "MỚI" bên dưới thẳng vào vòng
lặp của data_processing/main.py để không cần chạy lại script catch-up này nữa.

Cách chạy:
    python3 data_processing/export_scene_boundaries.py
"""

import os
from glob import glob

import torch
from transnetv2_pytorch import TransNetV2

SCENE_TXT_DIR = os.path.join("datasets", "transnetv2-scenes")
os.makedirs(SCENE_TXT_DIR, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[INFO] Using device: {device}")

transnetv2_weights_path = os.path.join(
    os.path.dirname(__import__("transnetv2_pytorch").__file__),
    "transnetv2-pytorch-weights.pth"
)
transnetv2_model = TransNetV2(device="auto")
transnetv2_model.eval()
transnetv2_state_dict = torch.load(transnetv2_weights_path, map_location=transnetv2_model.device)
transnetv2_model.load_state_dict(transnetv2_state_dict)
print(f"[INFO] TransNetV2 (pytorch) running on: {transnetv2_model.device}")

video_paths = glob(os.path.join("datasets", "videos", "*", "*.mp4"))
video_paths.sort()
print(f"[INFO] Found {len(video_paths)} videos")

skipped, done = 0, 0
for video_path in video_paths:
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    out_path = os.path.join(SCENE_TXT_DIR, f"{video_name}.mp4.scenes.txt")

    if os.path.exists(out_path):
        skipped += 1
        continue

    print(f"[INFO] Processing {video_name}...")
    video_frames, single_frame_predictions, all_frame_predictions = transnetv2_model.predict_video(video_path)
    single_frame_predictions_np = (
        single_frame_predictions.cpu().numpy() if hasattr(single_frame_predictions, "cpu")
        else single_frame_predictions
    )
    frame_ranges = transnetv2_model.predictions_to_scenes(single_frame_predictions_np)

    # Cùng định dạng "start end" mỗi dòng mà load_scene_vector_database.py parse bằng
    # `start, end = map(int, line.strip().split())`, và đuôi ".mp4.scenes.txt" nó strip
    # để lấy lại video_name.
    with open(out_path, "w") as f:
        for frame_range in frame_ranges:
            start, end = int(frame_range[0]), int(frame_range[1])
            f.write(f"{start} {end}\n")

    done += 1

print(f"[INFO] Done. Wrote {done} new .scenes.txt files, skipped {skipped} already present.")
print(f"[INFO] Next step: python3 backend/load_scene_vector_database.py (server stopped)")
