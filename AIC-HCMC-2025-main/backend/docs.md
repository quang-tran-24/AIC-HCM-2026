# Requirements
Required packages:
- deep-translator
- transformers
- torch
- pymilvus
- fastapi
- rapidfuzz

Install required packages with the following command:
```
pip install deep-translator transformers torch pymilvus fastapi rapidfuzz
```


# Files
1. `clip_vit_large_14_model.py`: CLIP ViT Large Patch 14 model by OpenAI

2. `vietnamese_to_english_translator.py`: Vietnamese to English translation service

3. `load_milvus_vector_database.py`: load vector database using milvus

4. `main.py`: backend server with retunred result as follows:


# Usage Instructions
1. Load and index the Milvus vector database:
```
python backend/load_milvus_vector_database.py
python backend/load_scene_vector_database.py
```

2. Start the backend server with FastAPI: 
```
uvicorn backend.main:app --reload
```
You may be waiting for 10 seconds to load the two models: openai/clip-vit-large-patch14 and Google Translator.

If you encounter issues related to Hugging Face authentication:
1. Log in to your Hugging Face account:
Visit https://huggingface.co/settings/tokens
2. Create a new access token.
3. Set the token in your terminal (replace <your_token> with the one you just created):
```
export HUGGING_FACE_HUB_TOKEN="<your_token>"
```


# API Usage

## Quick Search
**Request:** Send a POST request to the `/quick-search/` endpoint with a JSON body containing the search query in Vietnamese.
```json
{
  "text": "search query",
  "transcrip": "transcribed text",
  "ocr": "ocr text"
}
```

**Example Response:** The API returns a JSON object containing the translated text, a list of similar keyframes with their similarity scores, and a list of video rows with sorted keyframe paths.
```json
{
  "similar_frames": [
    {
        "video_name": "L21_V021",
        "keyframe_path": "datasets/keyframes/L21_V021/3478.jpg",
        "keyframe": "3478",
        "youtube_url": "https://youtube.com/watch?v=hTTaBTWWipY&t=115s",
        "similarity_score": 0.21533575654029846
    },
    {
        "video_name": "L22_V003",
        "keyframe_path": "datasets/keyframes/L22_V003/9246.jpg",
        "keyframe": "9246",
        "youtube_url": "https://youtube.com/watch?v=aJJUkV1L_Cw&t=369s",
        "similarity_score": 0.2075337916612625
    }
    ...
  ],
  "rows": [
    {
        "video_name": "L21_V021",
        "keyframe_paths": [
            "datasets/keyframes/L21_V021/3478.jpg",
            "datasets/keyframes/L21_V021/27167.jpg"
        ],
        "keyframes": [
            "3478",
            "27167"
        ],
        "youtube_links": [
            "https://youtube.com/watch?v=hTTaBTWWipY&t=115s",
            "https://youtube.com/watch?v=hTTaBTWWipY&t=905s"
        ],
        "transcript": "Background sounds are noticeable here."
    },
    {
        "video_name": "L22_V003",
        "keyframe_paths": [
            "datasets/keyframes/L22_V003/9246.jpg"
        ],
        "keyframes": [
            "9246"
        ],
        "youtube_links": [
            "https://youtube.com/watch?v=aJJUkV1L_Cw&t=369s"
        ],
        "transcript": "The speaker is introducing the topic."
    },
    ...
  ]
}
```

## Multi-keyframe Search
**Request:** Send a POST request to the `/multi-keyframe-search/` endpoint with a JSON body containing a list of keyframe_paths.
```json
{
  "keyframe_paths": [
      "datasets/keyframes/L21_V001/4.jpg",
      "datasets/keyframes/L21_V007/670.jpg",
      "datasets/keyframes/L22_V010/508.jpg"
  ],
  "text": "hello"
}
```

**Example Response:** The format is identical to /quick-search/, containing:
- `similar_frames`: list of similar keyframes with similarity scores
- `rows`: grouped keyframes by video, sorted by keyframe index


## Context Sequence
**Request:** Send a POST request to the `/context-sequence/` endpoint with a JSON body containing a single keyframe_path.
```json
{
  "keyframe_path": "datasets/keyframes/L22_V010/508.jpg"
}
```

**Example Response:** The response contains:
- `video_name`: the video of the given keyframe
- `frames`: ordered list of neighboring keyframes with their YouTube links
```json
{
  "video_name": "L22_V010",
  "frames": [
    {
        "keyframe_path": "datasets/keyframes/L22_V010/2.jpg",
        "youtube_url": "https://youtube.com/watch?v=TWcfxEOHxYk&t=0s"
    },
    {
        "keyframe_path": "datasets/keyframes/L22_V010/26.jpg",
        "youtube_url": "https://youtube.com/watch?v=TWcfxEOHxYk&t=1s"
    },
    ...
  ]
}
```


## Temporal Search
**Request:** Send a POST request to the `/temporal-search/` endpoint with a JSON body containing:
- `text1`: the first query text (e.g., beginning of an event).
- `text2`: the second query text (e.g., ending or continuation of the event).
```json
{
  "text1": "Introduction of the contest prizes",
  "text2": "Award ceremony presentation"
}
```

**Example Response:** The format is identical to `/quick-search/`, containing:
- `similar_frames`: is always empty (not yet implemented).
- `rows`: each row only contains 2 keyframes.


## Submit
This endpoint is used to submit a request with the given details of frames and answers.
Request Body:
```json
{
  "question_number": 1,
  "mode": 2,
  "selected_frames": [
    {
      "video_name": "L01_V001",
      "keyframe_idx": 12
    },
    {
      "video_name": "L01_V002",
      "keyframe_idx": 15
    }
  ],
  "answer": "two people"
}
```