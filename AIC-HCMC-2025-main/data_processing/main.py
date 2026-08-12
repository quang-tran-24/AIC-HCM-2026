import os
from glob import glob 
#from stuff.run_transnetv2 import TransNetV2
#from transnetv2 import TransNetV2
from transnetv2_pytorch import TransNetV2
from frame_extract import extract_resize_and_save_frame
from transformers import CLIPModel
from transformers import AutoProcessor, AutoModelForZeroShotImageClassification
from PIL import Image
import torch
import numpy as np
from tqdm import tqdm


# Check and set up GPU if available
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[INFO] Using device: {device}")


# Define models
transnetv2_weights_path = os.path.join(
    os.path.dirname(__import__("transnetv2_pytorch").__file__),
    "transnetv2-pytorch-weights.pth"
)
transnetv2_model = TransNetV2(device="auto")
transnetv2_model.eval()
transnetv2_state_dict = torch.load(transnetv2_weights_path, map_location=transnetv2_model.device)
transnetv2_model.load_state_dict(transnetv2_state_dict)
print(f"[INFO] TransNetV2 (pytorch) running on: {transnetv2_model.device}")

clip14_processor    = AutoProcessor.from_pretrained("openai/clip-vit-large-patch14-336")
clip14_model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14-336")
#clip14_model        = AutoModelForZeroShotImageClassification.from_pretrained("openai/clip-vit-large-patch14-336")
clip14_model.to(device)
clip14_model.eval()


# Define paths
video_paths = glob(os.path.join("datasets", "videos", "*", "*.mp4"))
video_paths.sort()
print(f"[INFO] Found {len(video_paths)} videos existed in datasets/")


# Define destination directories
keyframes_directory     = os.path.join("datasets", "keyframes")
os.makedirs(keyframes_directory, exist_ok=True)
clip_features_directory = os.path.join("datasets", "clip-features")
os.makedirs(clip_features_directory, exist_ok=True)


# Run
for video_path in video_paths:
    video_frames, single_frame_predictions, all_frame_predictions = transnetv2_model.predict_video(video_path)
#    frame_ranges = transnetv2_model.predictions_to_scenes(single_frame_predictions)
    single_frame_predictions_np = single_frame_predictions.cpu().numpy() if hasattr(single_frame_predictions, "cpu") else single_frame_predictions
    frame_ranges = transnetv2_model.predictions_to_scenes(single_frame_predictions_np)

    # MỚI: lưu scene boundary cho TRAKE (backend/load_scene_vector_database.py cần)
    scene_txt_dir = os.path.join("datasets", "transnetv2-scenes")
    os.makedirs(scene_txt_dir, exist_ok=True)
    video_name_for_scenes = os.path.splitext(os.path.basename(video_path))[0]
    with open(os.path.join(scene_txt_dir, f"{video_name_for_scenes}.mp4.scenes.txt"), "w") as sf:
        for frame_range in frame_ranges:
            sf.write(f"{int(frame_range[0])} {int(frame_range[1])}\n")

    list_of_extracted_frame_index = []
    for frame_range in frame_ranges:
        start, end = frame_range[0], frame_range[1]
        middle = (start + end) // 2

        if end - start > 4:
            list_of_extracted_frame_index.extend([start + 1, middle, end - 1])
        else:
            list_of_extracted_frame_index.extend([start + 1, end - 1])

    video_name = os.path.splitext(os.path.basename(video_path))[0]

    keyframes_save_folder = os.path.join(keyframes_directory, video_name)
    os.makedirs(keyframes_save_folder, exist_ok=True)

    clip_feature_save_folder = os.path.join(clip_features_directory, video_name)
    os.makedirs(clip_feature_save_folder, exist_ok=True)

    for frame_index in tqdm(list_of_extracted_frame_index):
        frame_path = os.path.join(keyframes_save_folder, f"{frame_index}.png")
        extract_resize_and_save_frame(
            video_path,
            frame_index,
            frame_path,
            scale=0.5
        )

        image = Image.open(frame_path).convert("RGB")
        inputs = clip14_processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
#           clip14_vector_embedding = clip14_model.get_image_features(**inputs)
#            clip14_vector_embedding = clip14_vector_embedding / clip14_vector_embedding.norm(p=2, dim=-1, keepdim=True)
            clip14_vector_embedding = clip14_model.get_image_features(**inputs)
            if hasattr(clip14_vector_embedding, "image_embeds"):
                clip14_vector_embedding = clip14_vector_embedding.image_embeds
            elif hasattr(clip14_vector_embedding, "pooler_output"):
                clip14_vector_embedding = clip14_vector_embedding.pooler_output
            clip14_vector_embedding = clip14_vector_embedding / clip14_vector_embedding.norm(p=2, dim=-1, keepdim=True)


            clip14_vector_embedding_np = clip14_vector_embedding.cpu().numpy()
            np.save(os.path.join(clip_feature_save_folder, f"{frame_index}.npy"), clip14_vector_embedding_np)