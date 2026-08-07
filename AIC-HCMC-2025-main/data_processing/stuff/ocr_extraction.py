import os
from glob import glob
import json
from PIL import Image
import numpy as np
import easyocr
from collections import defaultdict

# ============ Cấu hình ============
INPUT_DIR = "keyframes"          # cấu trúc: keyframes/<video_name>/<frame>.jpg
OUTPUT_DIR = "ocr-json"          # mỗi video ra 1 file json: ocr-json/<video_name>.json
BATCH_SIZE = 16                  # chỉnh theo VRAM/CPU
DETAIL = 1                       # 1: lấy bbox, text, confidence
LANGS = ['en', 'vi']             # ngôn ngữ OCR
# =================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Khởi tạo EasyOCR (khởi tạo 1 lần)
reader = easyocr.Reader(LANGS)

# Liệt kê tất cả frame
keyframe_files = glob(os.path.join(INPUT_DIR, "*", "*.jpg"))
keyframe_files.sort()

# Tải các kết quả đã có để tránh chạy lại
video_ocr_results = {}
processed_frames = set()

for json_file in glob(os.path.join(OUTPUT_DIR, "*.json")):
    video_name = os.path.splitext(os.path.basename(json_file))[0]
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            video_ocr_results[video_name] = data
            for frame_name in data.keys():
                processed_frames.add((video_name, frame_name))
    except Exception as e:
        print(f"Error loading {json_file}: {e}")

# Chuẩn bị danh sách tác vụ cần xử lý (bỏ qua frame đã có)
tasks = []
for image_path in keyframe_files:
    video_name = os.path.basename(os.path.dirname(image_path))
    frame_name = os.path.splitext(os.path.basename(image_path))[0]
    if (video_name, frame_name) in processed_frames:
        print(f"⏩ Skipped {video_name}/{frame_name} (already processed)")
        continue
    tasks.append((video_name, frame_name, image_path))

if not tasks:
    print("✅ Không còn frame mới để OCR.")
else:
    print(f"🔎 Số frame cần OCR: {len(tasks)} (batch size = {BATCH_SIZE})")

# Hàm ghi kết quả cho từng video
def save_video_json(video_name):
    save_path = os.path.join(OUTPUT_DIR, f"{video_name}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(video_ocr_results[video_name], f, ensure_ascii=False, indent=4)
    print(f"💾 Updated {save_path}")

# Xử lý theo batch
idx = 0
while idx < len(tasks):
    batch = tasks[idx: idx + BATCH_SIZE]

    # Đọc ảnh vào RAM (numpy arrays); nếu RAM hạn chế có thể dùng đường dẫn trực tiếp,
    # nhưng readtext_batched hoạt động tốt với numpy arrays.
    images = []
    for _, _, image_path in batch:
        try:
            img = Image.open(image_path).convert("RGB")
            images.append(np.array(img))
        except Exception as e:
            images.append(None)
            print(f"Error opening {image_path}: {e}")

    # Gọi OCR theo batch (lọc bỏ ảnh None nếu có)
    valid_indices = [i for i, arr in enumerate(images) if arr is not None]
    valid_images = [images[i] for i in valid_indices]

    batch_results = []
    if valid_images:
        try:
            # Mỗi phần tử trong kết quả tương ứng một ảnh
            batch_results = reader.readtext_batched(valid_images, detail=DETAIL)
        except Exception as e:
            print(f"Error in readtext_batched at idx {idx}: {e}")
            # fallback: kết quả rỗng cho tất cả ảnh hợp lệ
            batch_results = [[] for _ in valid_images]
    else:
        batch_results = []

    # Gắn kết quả trở lại từng task
    video_names_touched = defaultdict(bool)
    vi = 0  # con trỏ trên batch_results

    for local_i, (video_name, frame_name, image_path) in enumerate(batch):
        if local_i in valid_indices:
            ocr_result = batch_results[vi]
            vi += 1
        else:
            ocr_result = []

        # Trích text lines theo format detail=1: [bbox, text, conf]
        text_lines = []
        try:
            for line in ocr_result:
                text_line = line[1] if isinstance(line, (list, tuple)) and len(line) >= 2 else str(line)
                text_lines.append(text_line)
        except Exception as e:
            print(f"Error parsing OCR result for {image_path}: {e}")

        if video_name not in video_ocr_results:
            video_ocr_results[video_name] = {}

        video_ocr_results[video_name][frame_name] = text_lines
        processed_frames.add((video_name, frame_name))
        video_names_touched[video_name] = True

        print(f"✅ OCR {video_name}/{frame_name}: {text_lines}")

    # Ghi file JSON cho các video đã cập nhật trong batch này
    for v in video_names_touched.keys():
        try:
            save_video_json(v)
        except Exception as e:
            print(f"Error saving JSON for {v}: {e}")

    idx += BATCH_SIZE

print("🎉 Hoàn tất OCR theo batch.")
