import glob
import os
import subprocess

video_folders = glob.glob("extracted/*/video/")

folders_to_skip = ["Videos_L21_a", "Videos_L22_a"]

video_folders.sort()

for video_folder in video_folders:
    # Get the parent folder name (e.g., "Videos_L21_a")
    parent_folder = os.path.basename(os.path.dirname(video_folder))

    if parent_folder in folders_to_skip:
        print(f"⏩ Skipping {parent_folder}")
        continue

    print(f"▶️ Processing {parent_folder}")
    subprocess.run(["transnetv2_pytorch", video_folder])
