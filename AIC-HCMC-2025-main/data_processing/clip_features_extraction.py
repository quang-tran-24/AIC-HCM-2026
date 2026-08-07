import os
from glob import glob 
from transformers import AutoProcessor, AutoModelForZeroShotImageClassification
from PIL import Image
import torch
import numpy as np
from tqdm import tqdm


# Check and set up GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[INFO] Using device: {device}")


# Define models
clip14_processor    = AutoProcessor.from_pretrained("openai/clip-vit-large-patch14")
clip14_model        = AutoModelForZeroShotImageClassification.from_pretrained("openai/clip-vit-large-patch14")
clip14_model.to(device)
clip14_model.eval()


# Define paths
videos_extracted_keyframes = glob(os.path.join("datasets", "keyframes", "*"))
videos_extracted_keyframes.sort()
print(f"[INFO] Found {len(videos_extracted_keyframes)} videos existed with extracted keyframes in datasets/keyframes")


# Define destination directories
clip_features_directory = os.path.join("datasets", "clip-features")
os.makedirs(clip_features_directory, exist_ok=True)


# Run
for keyframe_folder in videos_extracted_keyframes:
    extracted_keyframes_paths = glob(os.path.join(keyframe_folder, "*.png"))
    extracted_keyframes_paths.sort()

    video_name = os.path.splitext(os.path.basename(keyframe_folder))[0]
    clip_feature_save_folder = os.path.join(clip_features_directory, video_name)
    os.makedirs(clip_feature_save_folder, exist_ok=True)

    print(f"[INFO] CLIP features extraction for {video_name}")
    for keyframe_path in tqdm(extracted_keyframes_paths):
        frame_index = os.path.splitext(os.path.basename(keyframe_path))[0]

        image = Image.open(keyframe_path).convert("RGB")
        inputs = clip14_processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            clip14_vector_embedding = clip14_model.get_image_features(**inputs)
            clip14_vector_embedding = clip14_vector_embedding / clip14_vector_embedding.norm(p=2, dim=-1, keepdim=True)

            clip14_vector_embedding_np = clip14_vector_embedding.cpu().numpy().squeeze()
            np.save(os.path.join(clip_feature_save_folder, f"{frame_index}.npy"), clip14_vector_embedding_np)
