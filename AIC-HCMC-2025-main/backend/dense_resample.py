"""
Dense frame re-sampling for TRAKE stage-2 alignment.

Why this exists
----------------
TransNetV2 keyframes give ~2-3 frames per *scene* (start/mid/end). TRAKE ground-truth
windows are usually **under 10 frames wide** (see AIC-HCMC 2026 rules, section 1.3).
There is no way a sparse scene-level keyframe can land inside a <10-frame window by luck
often enough to score well. So once stage-1 has picked a video + a rough time window per
sub-event, we re-decode *just that window* at native fps and run CLIP on every frame in it.

Key design points
------------------
- ONE ffmpeg process per window (not one per frame like the reference scripts in
  data_processing/stuff/keyframe_extraction.py) -> much faster for a window of 1-4s.
- We do NOT trust the nominal start_frame/fps seek time. Input-side `-ss` seeking is fast
  but can land near (not exactly on) the requested timestamp, especially with B-frames.
  Instead we attach the `showinfo` filter and parse the *actual* decoded `pts_time` of every
  output frame, then convert that back to a real frame index with the video's fps. This is
  the only way to get frame-accurate indices out of a fast seek.
- `threads=1` is passed into `.input()` (not `.output()`) — per project learnings, AV1
  streams crash ffmpeg-python without this, and it must be on the input side.
- Frames are written to a temp dir under /tmp (WSL2 native ext4), never under /mnt/d/,
  since that mount is a known I/O bottleneck for file-heavy workloads on this setup.
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from typing import List, Optional

import ffmpeg
from PIL import Image

PTS_TIME_RE = re.compile(r"pts_time:([0-9]+\.?[0-9]*)")


@dataclass
class DenseFrame:
    frame_index: int   # real frame number in the source video (fps-aligned)
    pts_time: float     # decoded timestamp in seconds, as reported by ffmpeg
    image: Image.Image  # RGB PIL image


def extract_dense_window(
    video_path: str,
    fps: float,
    start_frame: int,
    end_frame: int,
    pad_seconds: float = 0.4,
    scale: float = 1.0,
    work_dir: Optional[str] = None,
) -> List[DenseFrame]:
    """
    Decode every native frame between [start_frame, end_frame] (inclusive, plus a small
    safety pad) from `video_path`, and return them as in-memory PIL images tagged with
    their *real* frame index.

    Args:
        video_path: path to the source .mp4
        fps: frame rate of the video (from datasets/fps.json)
        start_frame / end_frame: real frame indices bounding the window to resample
        pad_seconds: extra seconds decoded on each side as a safety margin against seek
            drift; the returned frames are still filtered back down to the true window
            plus this pad, so callers get a slightly wider net for free
        scale: optional downscale factor (0 < scale <= 1) to speed up decoding/encoding
            for very long windows; 1.0 = full resolution
        work_dir: optional explicit temp dir; defaults to a fresh dir under /tmp

    Returns:
        List[DenseFrame] sorted by frame_index, deduplicated by frame_index (keeps the
        first occurrence — ffmpeg can occasionally repeat a frame if vsync isn't exact).
    """
    if end_frame < start_frame:
        start_frame, end_frame = end_frame, start_frame
    if fps <= 0:
        raise ValueError(f"Invalid fps={fps} for {video_path}")

    seek_time = max(0.0, start_frame / fps - pad_seconds)
    duration = (end_frame - start_frame) / fps + 2 * pad_seconds

    cleanup = work_dir is None
    out_dir = work_dir or tempfile.mkdtemp(prefix="trake_dense_")
    os.makedirs(out_dir, exist_ok=True)
    out_pattern = os.path.join(out_dir, "frame_%06d.png")

    try:
        vf_chain = "showinfo"
        if scale < 1.0:
            vf_chain = f"scale=iw*{scale}:ih*{scale},showinfo"

        stream = (
            ffmpeg
            .input(video_path, ss=seek_time, t=duration, threads=1)  # threads in input(): AV1 fix
            .output(out_pattern, vf=vf_chain, vsync="0", start_number=0)
            # CRITICAL: without -copyts, ffmpeg resets pts_time to ~0 at the seek point
            # instead of reporting the frame's actual position in the source video, which
            # would silently corrupt every frame_index this function returns. See
            # tools/frame_index_sanity_check.py for how this was caught.
            .global_args("-copyts")
        )
        _, stderr = stream.run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
        stderr_text = stderr.decode("utf-8", errors="ignore")

        pts_times = [float(m.group(1)) for m in PTS_TIME_RE.finditer(stderr_text)]

        png_files = sorted(
            f for f in os.listdir(out_dir) if f.startswith("frame_") and f.endswith(".png")
        )

        if len(pts_times) != len(png_files):
            # Fall back to a naive linear mapping if showinfo parsing didn't line up
            # 1:1 with the decoded frames (rare, but better to degrade gracefully than crash).
            print(
                f"[WARN] dense_resample: showinfo count ({len(pts_times)}) != "
                f"frame count ({len(png_files)}) for {video_path}; falling back to "
                f"linear frame indexing from seek_time={seek_time:.3f}s"
            )
            pts_times = [seek_time + i / fps for i in range(len(png_files))]

        frames: List[DenseFrame] = []
        seen_indices = set()
        for png_name, pts_time in zip(png_files, pts_times):
            real_index = round(pts_time * fps)
            if real_index in seen_indices:
                continue
            seen_indices.add(real_index)
            img = Image.open(os.path.join(out_dir, png_name)).convert("RGB")
            img.load()  # force read before the temp file is deleted
            frames.append(DenseFrame(frame_index=real_index, pts_time=pts_time, image=img))

        frames.sort(key=lambda f: f.frame_index)
        return frames

    except ffmpeg.Error as e:
        stderr_text = e.stderr.decode("utf-8", errors="ignore") if e.stderr else str(e)
        raise RuntimeError(f"ffmpeg failed extracting window from {video_path}: {stderr_text}")
    finally:
        if cleanup:
            shutil.rmtree(out_dir, ignore_errors=True)
