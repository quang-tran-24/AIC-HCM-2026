from glob import glob
import os
import subprocess
import cv2

def extract_resize_and_save_frame_ffmpeg(video_path, frame_id, save_path, scale=0.5):
    if scale <= 0 or scale > 1:
        raise ValueError("Scale must be between 0 and 1 (exclusive of 0)")
    
    # Get the frame rate of the video
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate', '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        fps_str = result.stdout.strip()
        if '/' in fps_str:
            num, den = fps_str.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(fps_str)
        
        timestamp = frame_id / fps
        
        # Use ffmpeg to extract the frame
        cmd = [
            'ffmpeg', '-ss', str(timestamp), '-i', video_path,
            '-vframes', '1', '-vf', f'scale=iw*{scale}:ih*{scale}',
            '-q:v', '2', '-y', save_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg failed: {e.stderr}")
    except Exception as e:
        raise RuntimeError(f"Error: {e}")

destination = "keyframes/"
video_paths = glob("extracted/*/video/*.mp4")

for video_path in video_paths:
    scenes_txt_file = video_path + ".scenes.txt"
    
    if not os.path.exists(scenes_txt_file):
        print(f"⚠️ Cannot find {scenes_txt_file}, skipping")
        continue

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_folder = os.path.join(destination, video_name)
    os.makedirs(video_folder, exist_ok=True)

    with open(scenes_txt_file, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            start, end = map(int, parts)

            if end - start < 60:
                frames_to_extract = [(start + end) // 2]
            else:
                frames_to_extract = [start + 5, (start + end) // 2, end - 5]

            for frame_id in frames_to_extract:
                save_path = os.path.join(video_folder, f"{frame_id}.jpg")
                if os.path.exists(save_path):
                    print(f"✔ {save_path} already exists, skipping extraction")
                    continue
                try:
                    extract_resize_and_save_frame_ffmpeg(video_path, frame_id, save_path, scale=0.5)
                    print(f"✔ Saved {save_path}")
                except Exception as e:
                    print(f"❌ Error processing frame {frame_id} of {video_path}: {e}")