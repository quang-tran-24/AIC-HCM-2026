# Reranking (stage 1: OCR + transcript + neighbor fusion) — integration guide

## What's in this drop

```
backend/rerank.py   new — normalizes OCR/transcript scores to [0,1], adds neighbor-
                     consistency scoring, and replaces the lexicographic sort with an
                     actual weighted fusion.
```

No new dependencies — only `numpy`, already used everywhere in the backend.

## The bug this fixes

In `backend/api/quick_search.py`, the final ranking is:

```python
rows = sorted(rows, key=lambda x: (
    x.get("similarity_score", 0), x.get("transcript_score", 0),
    x.get("ocr_score", 0), len(x.get("keyframes", []))
), reverse=True)
```

That's a lexicographic (tuple) sort: rows are compared by `similarity_score` first, and
`transcript_score`/`ocr_score` only matter to break an *exact tie* on that float. Since
CLIP cosine floats essentially never tie, transcript and OCR currently have **zero
effect on ranking** — they only acted earlier as a binary keep/drop filter. Confirmed
with a synthetic test: a candidate with CLIP=0.70 but almost no OCR match always beat a
candidate with CLIP=0.68 and a near-perfect OCR match under the old sort, every time.
`rerank_candidates()` fixes that — see the test in the block below for the same case
flipping to the right order.

## Required changes to `backend/api/quick_search.py`

### 1. Track which keyframe each row's best score came from

The current row-building loop keeps `best_similarity_score = max(similarity_scores)` but
throws away *which* keyframe that came from — needed so the neighbor-consistency check
knows which frame to look around. Add one field:

```python
# around line 681-698, inside the row-building loop:
rows = []
for video_name, keyframe_items in video_keyframes.items():
    keyframe_items.sort(key=lambda x: int(x[2]))
    keyframe_paths, youtube_links, keyframes, ocr_texts, similarity_scores = zip(
        *[(p, u, str(idx), (ocr or ""), sim_score) for p, u, idx, ocr, sim_score in keyframe_items]
    )

    best_similarity_score = max(similarity_scores)
    best_idx = max(range(len(similarity_scores)), key=lambda i: similarity_scores[i])

    rows.append({
        "video_name": video_name,
        "keyframe_paths": keyframe_paths,
        "keyframes": keyframes,
        "youtube_links": youtube_links,
        "ocr_text": ocr_texts,
        "similarity_score": best_similarity_score,
        "keyframe_index": int(keyframes[best_idx]),   # <-- new, needed by rerank_candidates
    })
```

### 2. Replace the sort block

```python
# around line 753-759, replace:
rows = sorted(rows, key=lambda x: (
    x.get("similarity_score", 0), x.get("transcript_score", 0),
    x.get("ocr_score", 0), len(x.get("keyframes", []))
), reverse=True)

# with:
from backend.rerank import rerank_candidates

rows = rerank_candidates(
    rows,
    query_vector=vector,  # the CLIP text vector already computed earlier in process_text()
    milvus_keyframe_client=request.app.state.milvus_keyframe,
    has_transcript_query=bool(transcript_query),
    has_ocr_query=bool(ocr_query),
)
```

That's it — `rerank_candidates` mutates each row with `neighbor_score` and `final_score`
and returns them sorted. Nothing else in the function needs to change; `rows` still has
the same shape the frontend already expects, just two extra numeric fields.

## Tuning

Default weights in `RerankWeights` (`backend/rerank.py`): `clip=0.65, transcript=0.15,
ocr=0.10, neighbor=0.10`. These are hand-picked starting points, not tuned against real
queries yet. Once you have a handful of dev queries with known correct answers, worth
sweeping these (e.g. grid search clip weight in [0.5, 0.8]) and checking which setting
maximizes R@1 on that dev set — that's the natural next step after this lands, rather
than guessing further by hand.

`neighbor_window` (default 2 in `rerank_candidates`) controls how many positionally-
adjacent keyframes get averaged in. Wider window = smoother but slower (more Milvus
`.query()` calls the first time each video is touched — results are cached per video in
`_VIDEO_VECTOR_CACHE` after the first hit, same caching pattern quick_search.py already
uses for `KEYFRAME_CACHE`).

## What's intentionally NOT in this drop

Object detection (Faster R-CNN) scoring — you confirmed the data's ready, but you asked
to land OCR+neighbor first since it's a smaller, faster change. That's next in line
whenever you want it; it'll plug into the same `combine_scores()`/`RerankWeights`
machinery as a fifth term, so this module is already shaped to take it without a rewrite.
