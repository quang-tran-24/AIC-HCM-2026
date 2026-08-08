"""
Continuous score fusion for search results (stage 1 of the reranking work).

Problem this fixes
-------------------
backend/api/quick_search.py currently sorts results with:

    sorted(rows, key=lambda x: (x["similarity_score"], x["transcript_score"], x["ocr_score"], ...))

This is a *lexicographic* sort, not a weighted fusion. Because similarity_score is a
float CLIP cosine value that's essentially never exactly equal between two rows,
transcript_score and ocr_score can only ever break ties that don't happen in practice —
they're computed, attached to each row, and then have zero real effect on ranking. OCR
and transcript currently only act as a binary keep/drop filter earlier in the function.

This module replaces that with an actual weighted combination of normalized scores, plus
a neighbor-consistency signal that wasn't present before at all: a candidate whose
positionally-adjacent keyframes also score well against the query is more likely to be a
real match than an isolated single-frame spike (CLIP noise on one frame).

Scale note
----------
CLIP cosine similarity from Milvus (metric_type=COSINE) is in roughly [0, 1] for these
embeddings. transcript/ocr scores from quick_search.py's `is_text_match()` are on a
0-100+ scale (100 = fuzzy match at the threshold, count*100 for substring hits, so it
can exceed 100 for multiple occurrences). `normalize_match_score` maps those onto the
same [0, 1] scale so the weighted sum in `combine_scores` is meaningful.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class RerankWeights:
    clip: float = 0.65
    transcript: float = 0.15
    ocr: float = 0.10
    neighbor: float = 0.10

    def normalized(self) -> "RerankWeights":
        """Weights active for a given query redistribute to sum to 1 (see combine_scores)."""
        total = self.clip + self.transcript + self.ocr + self.neighbor
        if total <= 0:
            return RerankWeights(1.0, 0.0, 0.0, 0.0)
        return RerankWeights(self.clip / total, self.transcript / total, self.ocr / total, self.neighbor / total)


def normalize_match_score(raw_score: float, cap: float = 100.0) -> float:
    """Map quick_search.py's is_text_match() output (0-100+, uncapped for multi-hit
    substring matches) onto [0, 1] so it's on the same scale as CLIP cosine similarity."""
    if raw_score <= 0:
        return 0.0
    return min(raw_score, cap) / cap


# ---------------------------------------------------------------------------
# Neighbor consistency
# ---------------------------------------------------------------------------

_VIDEO_VECTOR_CACHE: Dict[str, List[Tuple[int, np.ndarray]]] = {}


def get_video_keyframe_vectors(video_name: str, milvus_keyframe_client) -> List[Tuple[int, np.ndarray]]:
    """(keyframe_index, clip_feature_vector) pairs for a video, sorted by keyframe_index.
    Cached per video_name — separate from quick_search.py's own KEYFRAME_CACHE since that
    one doesn't fetch the vector field, and we don't want to change its shape for callers
    that don't need vectors.
    """
    if video_name in _VIDEO_VECTOR_CACHE:
        return _VIDEO_VECTOR_CACHE[video_name]

    results = milvus_keyframe_client.query(
        collection_name="keyframe_vectors",
        filter=f'video_name == "{video_name}"',
        output_fields=["keyframe_index", "clip_feature_vector"],
    )

    pairs = []
    for item in results or []:
        try:
            idx = int(item["keyframe_index"])
            vec = np.array(item["clip_feature_vector"], dtype=np.float32)
        except (KeyError, TypeError, ValueError):
            continue
        pairs.append((idx, vec))

    pairs.sort(key=lambda p: p[0])
    _VIDEO_VECTOR_CACHE[video_name] = pairs
    return pairs


def neighbor_consistency_score(
    video_name: str,
    keyframe_index: int,
    query_vector: np.ndarray,
    milvus_keyframe_client,
    window: int = 2,
) -> float:
    """
    Average cosine similarity between the query and the keyframes positionally adjacent
    to (video_name, keyframe_index) in that video's sorted keyframe list — NOT adjacent by
    frame-index distance, since TransNetV2 keyframes are spaced irregularly. Weighted by
    1/(1+position_distance) so the closest neighbors count most. Returns 0.0 if the
    candidate has no neighbors (e.g. it's the only keyframe in the video, or wasn't found).
    """
    pairs = get_video_keyframe_vectors(video_name, milvus_keyframe_client)
    if len(pairs) < 2:
        return 0.0

    pos = next((i for i, (idx, _) in enumerate(pairs) if idx == keyframe_index), None)
    if pos is None:
        return 0.0

    q = query_vector / (np.linalg.norm(query_vector) + 1e-8)

    weighted_sum = 0.0
    weight_total = 0.0
    for offset in range(1, window + 1):
        for neighbor_pos in (pos - offset, pos + offset):
            if 0 <= neighbor_pos < len(pairs):
                _, vec = pairs[neighbor_pos]
                v = vec / (np.linalg.norm(vec) + 1e-8)
                sim = float(np.dot(q, v))
                w = 1.0 / (1 + offset)
                weighted_sum += w * sim
                weight_total += w

    if weight_total == 0:
        return 0.0
    return weighted_sum / weight_total


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------

def combine_scores(
    clip_score: float,
    transcript_score_raw: float = 0.0,
    ocr_score_raw: float = 0.0,
    neighbor_score: float = 0.0,
    has_transcript_query: bool = False,
    has_ocr_query: bool = False,
    weights: RerankWeights = RerankWeights(),
) -> float:
    """
    Weighted fusion of the four signals, on a comparable [0, 1]-ish scale.

    Weight redistribution: if the query didn't include a transcript/OCR string at all,
    that signal is meaningless (raw score is always 0 for every candidate) and its weight
    would just shrink every score by the same constant without changing the ranking — but
    we redistribute it to `clip` anyway so scores stay comparable across different query
    shapes (a text-only query and a text+ocr query end up on the same overall scale).
    """
    active = RerankWeights(
        clip=weights.clip,
        transcript=weights.transcript if has_transcript_query else 0.0,
        ocr=weights.ocr if has_ocr_query else 0.0,
        neighbor=weights.neighbor,
    ).normalized()

    return (
        active.clip * clip_score
        + active.transcript * normalize_match_score(transcript_score_raw)
        + active.ocr * normalize_match_score(ocr_score_raw)
        + active.neighbor * neighbor_score
    )


def rerank_candidates(
    candidates: List[dict],
    query_vector: np.ndarray,
    milvus_keyframe_client,
    has_transcript_query: bool = False,
    has_ocr_query: bool = False,
    weights: RerankWeights = RerankWeights(),
    neighbor_window: int = 2,
) -> List[dict]:
    """
    candidates: list of dicts, each needing at least:
        video_name, keyframe_index (int), similarity_score (CLIP cosine),
        transcript_score (raw, default 0), ocr_score (raw, default 0)

    Returns the same dicts (mutated in place, also returned) with a new "final_score"
    field, sorted descending by it. Component scores are kept on each dict as
    "neighbor_score" / "final_score" for debugging or surfacing in the UI.
    """
    for c in candidates:
        n_score = neighbor_consistency_score(
            c["video_name"], int(c["keyframe_index"]), query_vector,
            milvus_keyframe_client, window=neighbor_window,
        )
        c["neighbor_score"] = n_score
        c["final_score"] = combine_scores(
            clip_score=c.get("similarity_score", 0.0),
            transcript_score_raw=c.get("transcript_score", 0.0),
            ocr_score_raw=c.get("ocr_score", 0.0),
            neighbor_score=n_score,
            has_transcript_query=has_transcript_query,
            has_ocr_query=has_ocr_query,
            weights=weights,
        )

    candidates.sort(key=lambda c: c["final_score"], reverse=True)
    return candidates
