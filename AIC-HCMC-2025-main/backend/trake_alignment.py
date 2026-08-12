"""
TRAKE alignment: video retrieval + per-event semantic-keyframe alignment.

Pipeline (matches AIC-HCMC 2026 rules, section 1.3):
  Stage 1 - Retrieval:  pick the ONE video whose scene sequence best matches the
                         ordered E1..En sub-events (coarse, scene-granularity).
  Stage 2 - Alignment:  for each event, re-decode a short window of the chosen video
                         at native fps and pick the single best-matching frame
                         (dense, frame-granularity). This is the part that matters most:
                         ground-truth windows are usually <10 frames wide, which sparse
                         TransNetV2 keyframes cannot reliably hit.

This module is transport-agnostic: pass it a Milvus client, the CLIP model wrapper, and
a translator, and it works whether called from a FastAPI route (backend/api/trake_search.py)
or a CLI script (tools/trake_cli.py).

Known bugs this fixes relative to the current backend/api/temporal_search.py:
  - `limit=1000` in the scenes.query() call silently truncates the scene pool once a
    dataset grows past 1000 scenes, biasing which videos can even be found. Here we pass
    an explicit large limit.
  - `app.state.milvus_scene` is never initialized in backend/main.py's startup_event
    (the block that creates it is commented out) even though temporal_search.py reads
    it — see INTEGRATION.md for the one-line fix.
  - temporal_search.py only ever matches exactly 2 consecutive scenes. This module
    generalizes to N ordered events (TRAKE queries have anywhere from 2 to ~5+ events)
    via a monotonic DP instead of a hardcoded pairwise loop.
"""

import os
import re
from glob import glob
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from backend.dense_resample import extract_dense_window

EVENT_LINE_RE = re.compile(r"^E(\d+)\s*:\s*(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Query parsing
# ---------------------------------------------------------------------------

def parse_trake_query(query_text: str) -> Tuple[str, List[str]]:
    """
    Parse the raw contents of a query-*-trake.txt file into (context_sentence, [E1, E2, ...]).
    Matches the format used throughout queries/**/query-*-trake.txt:
        <optional context sentence>
        E1: <text>
        E2: <text>
        ...
    """
    matches = sorted(
        ((int(m.group(1)), m.group(2).strip()) for m in EVENT_LINE_RE.finditer(query_text)),
        key=lambda x: x[0],
    )
    if not matches:
        raise ValueError("No 'E<k>: ...' lines found in TRAKE query text")

    event_texts = [text for _, text in matches]

    first_event_pos = query_text.find(f"E{matches[0][0]}:")
    context = query_text[:first_event_pos].strip() if first_event_pos > 0 else ""

    return context, event_texts


# ---------------------------------------------------------------------------
# Stage 1: coarse multi-event localization (scene granularity)
# ---------------------------------------------------------------------------

def fetch_all_scenes(milvus_scene_client, collection_name: str = "scene_vectors") -> Dict[str, List[dict]]:
    """
    Pull every row from scene_vectors, grouped by video_name and sorted by scene_index.

    NOTE: explicitly passes a large `limit`. The existing temporal_search.py hardcodes
    limit=1000 on this same query, which silently drops scenes (and therefore whole
    videos) once the dataset grows past 1000 total scenes. That bug is why this is a
    standalone helper instead of copy-pasted inline.
    """
    rows = milvus_scene_client.query(
        collection_name=collection_name,
        output_fields=[
            "video_name", "scene_index", "start_frame", "end_frame",
            "mid_frame", "scene_feature_vector",
        ],
        limit=1_000_000,
    )

    by_video: Dict[str, List[dict]] = {}
    for row in rows or []:
        vec = np.array(row["scene_feature_vector"], dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        by_video.setdefault(row["video_name"], []).append({
            "video_name": row["video_name"],
            "scene_index": int(row["scene_index"]),
            "start_frame": int(row["start_frame"]),
            "end_frame": int(row["end_frame"]),
            "mid_frame": int(row["mid_frame"]),
            "scene_feature_vector": vec,
        })

    for video_name in by_video:
        by_video[video_name].sort(key=lambda s: s["scene_index"])

    return by_video


def _monotonic_best_path(sim_matrix: np.ndarray) -> Tuple[float, List[int]]:
    """
    sim_matrix[i, k] = cosine similarity between scene i and event k, shape (M, N).

    Returns the (score, [scene_idx_for_event_0, ..., scene_idx_for_event_{N-1}]) that
    maximizes the sum of per-event similarity subject to scene indices being strictly
    increasing (events happen in chronological order; not every scene needs to be used).

    Classic O(M*N) DP with a running prefix-max, same idea as the two-event brute-force
    loop in temporal_search.py, generalized to N events.
    """
    M, N = sim_matrix.shape
    if M < N or N == 0:
        return float("-inf"), []

    NEG_INF = float("-inf")
    dp = np.full((N, M), NEG_INF, dtype=np.float64)
    parent = np.full((N, M), -1, dtype=int)

    dp[0, :] = sim_matrix[:, 0]

    for k in range(1, N):
        running_best = NEG_INF
        running_best_idx = -1
        for i in range(M):
            if running_best > NEG_INF:
                dp[k, i] = running_best + sim_matrix[i, k]
                parent[k, i] = running_best_idx
            if dp[k - 1, i] > running_best:
                running_best = dp[k - 1, i]
                running_best_idx = i

    best_last = int(np.argmax(dp[N - 1, :]))
    best_score = float(dp[N - 1, best_last])
    if best_score == NEG_INF:
        return float("-inf"), []

    path = [0] * N
    cur = best_last
    for k in range(N - 1, -1, -1):
        path[k] = cur
        cur = parent[k, cur]

    return best_score, path


def coarse_localize(
    event_vectors: np.ndarray,
    scenes_by_video: Dict[str, List[dict]],
) -> Optional[dict]:
    """
    Find the single best video for an ordered sequence of event queries.

    event_vectors: (N, 768) L2-normalized CLIP text embeddings, one per E<k>.
    Returns {"video_name", "score", "scenes": [scene_dict per event, in order]} or None
    if no video has enough scenes to even hold N ordered events.
    """
    best = None
    for video_name, scenes in scenes_by_video.items():
        if len(scenes) < event_vectors.shape[0]:
            continue
        scene_vecs = np.stack([s["scene_feature_vector"] for s in scenes])  # (M, 768)
        sim_matrix = scene_vecs @ event_vectors.T  # (M, N), both sides unit-normalized
        score, path = _monotonic_best_path(sim_matrix)
        if not path:
            continue
        if best is None or score > best["score"]:
            best = {
                "video_name": video_name,
                "score": score,
                "scenes": [scenes[i] for i in path],
            }
    return best


# ---------------------------------------------------------------------------
# Stage 2: dense re-sampling refinement (frame granularity)
# ---------------------------------------------------------------------------

def dense_refine_events(
    video_path: str,
    fps: float,
    coarse_scenes: List[dict],
    event_vectors: np.ndarray,
    clip_model,
    video_name: str,
    pad_seconds: float = 0.4,
    max_window_seconds: float = 3.0,
    dense_frame_cache_dir: str = os.path.join("datasets", "keyframes_dense"),
) -> Tuple[List[int], List[str]]:
    """
    For each event, re-decode a short window around its coarse scene at native fps and
    pick the frame whose CLIP embedding best matches that event's text query.

    Window bounds per event k are clamped to the midpoint between neighboring events'
    coarse mid_frames, so windows never overlap and stay chronologically ordered — a
    refine step can never "steal" a frame that belongs to the next event.

    The winning frame's image is saved under `dense_frame_cache_dir` before the rest of
    the decoded window is discarded — dense-resampled frames don't correspond to any
    file that already exists on disk (unlike the sparse pre-extracted keyframes), so
    without this there'd be nothing for a UI to display for a TRAKE result.

    Returns (frame_ids, frame_paths) — parallel lists, one entry per event, in order.
    """
    n = len(coarse_scenes)
    mid_frames = [s["mid_frame"] for s in coarse_scenes]
    max_window_frames = int(max_window_seconds * fps)

    video_cache_dir = os.path.join(dense_frame_cache_dir, video_name)
    os.makedirs(video_cache_dir, exist_ok=True)

    refined_frame_ids: List[int] = []
    refined_frame_paths: List[str] = []
    for k, scene in enumerate(coarse_scenes):
        left_bound = scene["start_frame"] if k == 0 else (mid_frames[k - 1] + mid_frames[k]) // 2
        right_bound = scene["end_frame"] if k == n - 1 else (mid_frames[k] + mid_frames[k + 1]) // 2

        if right_bound - left_bound > max_window_frames:
            center = scene["mid_frame"]
            left_bound = max(left_bound, center - max_window_frames // 2)
            right_bound = min(right_bound, center + max_window_frames // 2)

        left_bound = max(0, left_bound)
        right_bound = max(right_bound, left_bound + 1)

        frames = extract_dense_window(video_path, fps, left_bound, right_bound, pad_seconds=pad_seconds)

        if not frames:
            print(
                f"[WARN] trake_alignment: no frames decoded for event {k + 1} "
                f"window [{left_bound}, {right_bound}] in {video_path}; "
                f"falling back to coarse mid_frame={scene['mid_frame']}"
            )
            fallback_id = scene["mid_frame"]
            refined_frame_ids.append(fallback_id)
            # No decoded image to save in the fallback case; point at the sparse
            # keyframe path convention as a best-effort guess (may 404 if this exact
            # mid_frame wasn't one of the originally-extracted keyframes).
            refined_frame_paths.append(
                os.path.join("datasets", "keyframes", video_name, f"{fallback_id}.jpg")
            )
            continue

        images = [f.image for f in frames]
        image_vecs = clip_model.embed_images(images)
        if image_vecs.ndim == 1:
            image_vecs = image_vecs[None, :]

        sims = image_vecs @ event_vectors[k]
        best_i = int(np.argmax(sims))
        best_frame = frames[best_i]

        frame_path = os.path.join(video_cache_dir, f"{best_frame.frame_index}.jpg")
        try:
            best_frame.image.save(frame_path, quality=90)
        except Exception as e:
            print(f"[WARN] trake_alignment: failed to save dense frame image {frame_path}: {e}")

        refined_frame_ids.append(best_frame.frame_index)
        refined_frame_paths.append(frame_path)

    return refined_frame_ids, refined_frame_paths


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def default_video_path_resolver(video_name: str, videos_root: str = os.path.join("datasets", "videos")) -> str:
    matches = glob(os.path.join(videos_root, "*", f"{video_name}.mp4"))
    if not matches:
        raise FileNotFoundError(f"Could not locate video file for '{video_name}' under {videos_root}")
    return matches[0]


def run_trake_query(
    query_text: str,
    milvus_scene_client,
    clip_model,
    translator,
    fps_dict: Dict[str, float],
    video_path_resolver: Callable[[str], str] = default_video_path_resolver,
    include_context: bool = True,
    forced_video_name: Optional[str] = None,
) -> dict:
    """
    Full pipeline: parse -> translate -> embed -> coarse localize -> dense refine.

    forced_video_name: skip stage 1 and refine directly on a known video. Useful during
    development/debugging when you already know the ground-truth video and just want to
    validate stage-2 precision in isolation.
    """
    context, event_texts_vi = parse_trake_query(query_text)
    if len(event_texts_vi) < 2:
        raise ValueError("TRAKE query must contain at least 2 'E<k>:' lines")

    query_strings_en = []
    for ev in event_texts_vi:
        vi_text = f"{context} {ev}".strip() if include_context and context else ev
        query_strings_en.append(translator.translate(vi_text))

    event_vectors = np.stack([clip_model.embed(q) for q in query_strings_en])  # (N, 768)

    if forced_video_name:
        scenes_by_video = fetch_all_scenes(milvus_scene_client)
        scenes = scenes_by_video.get(forced_video_name)
        if not scenes:
            raise ValueError(f"No scenes found for forced_video_name='{forced_video_name}'")
        scene_vecs = np.stack([s["scene_feature_vector"] for s in scenes])
        sim_matrix = scene_vecs @ event_vectors.T
        score, path = _monotonic_best_path(sim_matrix)
        if not path:
            raise ValueError(f"'{forced_video_name}' does not have enough scenes for {len(event_texts_vi)} events")
        coarse = {"video_name": forced_video_name, "score": score, "scenes": [scenes[i] for i in path]}
    else:
        scenes_by_video = fetch_all_scenes(milvus_scene_client)
        coarse = coarse_localize(event_vectors, scenes_by_video)
        if coarse is None:
            raise RuntimeError("No video in scene_vectors has enough scenes to match this TRAKE query")

    video_name = coarse["video_name"]
    fps = fps_dict.get(video_name)
    if not fps:
        raise RuntimeError(f"No fps entry for '{video_name}' in datasets/fps.json")

    video_path = video_path_resolver(video_name)
    frame_ids, frame_paths = dense_refine_events(
        video_path, fps, coarse["scenes"], event_vectors, clip_model, video_name=video_name,
    )

    return {
        "video_name": video_name,
        "frame_ids": frame_ids,
        "frame_paths": frame_paths,
        "coarse_score": coarse["score"],
        "num_events": len(event_texts_vi),
        "event_texts_vi": event_texts_vi,
        "event_texts_en": query_strings_en,
    }