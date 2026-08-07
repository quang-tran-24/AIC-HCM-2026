import os
from glob import glob 
from stuff.run_transnetv2 import TransNetV2
from frame_extract import extract_resize_and_save_frame
from tqdm import tqdm


# Define model
transnetv2_model    = TransNetV2()


# Define paths
video_paths = glob(os.path.join("datasets", "videos", "*", "*.mp4"))
video_paths.sort()
print(f"[INFO] Found {len(video_paths)} videos existed in datasets/")


# Define destination directories
keyframes_directory     = os.path.join("datasets", "keyframes")
os.makedirs(keyframes_directory, exist_ok=True)


# Run
for video_path in video_paths:
    video_frames, single_frame_predictions, all_frame_predictions = transnetv2_model.predict_video(video_path)
    frame_ranges = transnetv2_model.predictions_to_scenes(single_frame_predictions)

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

    for frame_index in tqdm(list_of_extracted_frame_index):
        frame_path = os.path.join(keyframes_save_folder, f"{frame_index}.png")
        extract_resize_and_save_frame(
            video_path,
            frame_index,
            frame_path,
            scale=0.5
        )
