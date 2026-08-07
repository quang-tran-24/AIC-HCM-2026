import cv2

def extract_and_save_frame(video_path, frame_id, save_path):
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if frame_id < 0 or frame_id >= total_frames:
        cap.release()
        raise IndexError(f"frame_id {frame_id} is out of range (0 to {total_frames - 1})")
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
    success, frame = cap.read()
    cap.release()
    
    if not success:
        raise RuntimeError(f"Failed to read frame at position {frame_id}")
    
    success = cv2.imwrite(save_path, frame)
    if not success:
        raise RuntimeError(f"Failed to write frame to {save_path}")


def extract_resize_and_save_frame(video_path, frame_id, save_path, scale=0.5):
    if scale <= 0 or scale > 1:
        raise ValueError("Scale must be between 0 and 1 (exclusive of 0)")

    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if frame_id < 0 or frame_id >= total_frames:
        cap.release()
        raise IndexError(f"frame_id {frame_id} is out of range (0 to {total_frames - 1})")
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
    success, frame = cap.read()
    cap.release()
    
    if not success:
        raise RuntimeError(f"Failed to read frame at position {frame_id}")
    
    # Resize the frame
    height, width = frame.shape[:2]
    new_size = (int(width * scale), int(height * scale))
    resized_frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
    
    success = cv2.imwrite(save_path, resized_frame)
    if not success:
        raise RuntimeError(f"Failed to write resized frame to {save_path}")
