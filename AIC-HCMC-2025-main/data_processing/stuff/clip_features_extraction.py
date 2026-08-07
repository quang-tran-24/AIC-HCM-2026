import os
from glob import glob
from transformers import CLIPProcessor, CLIPModel
import torch
import numpy as np
from PIL import Image

device = "cuda"
print(f"[INFO] Using device: {device}")

clip14_processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14-336")
clip14_model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14-336")
clip14_model.to(device)
clip14_model.eval()

# Chỉ lấy các video thuộc nhóm L21 (L21_V001, L21_V002, ...)
DATASETS_DIR = os.path.join("..", "..", "datasets")
keyframe_files = glob(os.path.join(DATASETS_DIR, "keyframes", "L21_*", "*.jpg"))
keyframe_files.sort()
print(f"[INFO] Found {len(keyframe_files)} keyframes for L21")

destination = os.path.join(DATASETS_DIR, "clip-features")
os.makedirs(destination, exist_ok=True)

for img_path in keyframe_files:
    video_name = os.path.basename(os.path.dirname(img_path))
    frame_name = os.path.splitext(os.path.basename(img_path))[0]
    save_folder = os.path.join(destination, video_name)
    os.makedirs(save_folder, exist_ok=True)
    save_path = os.path.join(save_folder, f"{frame_name}.npy")

    if os.path.exists(save_path):
        print(f"⏩ Skipped {save_path} (already exists)")
        continue

    try:
        image = Image.open(img_path).convert("RGB")
        inputs = clip14_processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = clip14_model.get_image_features(**inputs)
            image_features_tensor = outputs.pooler_output  # transformers v5.x: embedding nằm ở đây

        features = image_features_tensor.cpu().numpy().astype(np.float32)
        features = features / np.linalg.norm(features, axis=-1, keepdims=True)

        np.save(save_path, features)
        print(f"✔ Saved {save_path}")

    except Exception as e:
        print(f"❌ Error processing {img_path}: {e}")