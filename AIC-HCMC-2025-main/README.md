# HCMC-AIC-2025
The source code repository for The 2025 Ho Chi Minh City AI Challenge by team KPT.

Team members: Thinh-Phat Vo, Quang-Thang Duong, Quoc-Thang Nguyen, Dang-Khoa Mai, and Nguyen-Khang Ly (all from Vietnam National University, Ho Chi Minh City).


# Project Structure
The repository is organized into the following main folders:

- **datasets**: contains all the raw/processed data used in the project, these data are then indexed in the databases.

- **data_processing**: contains the source code for the data processing and features extraction task.

- **frontend**: provides the web interface for user interaction and result visualization.

- **backend**: hosts the server-side code, including API endpoints and the database loaded from `datasets`.



# Datasets Structure
```
datasets/
├── videos/
│   ├── batch_1/
│   │   ├── L01_V001.mp4
│   │   ├── ...
│   ├── batch_2/
│   │   ├── L10_V001.mp4
│   │   ├── ...
│   ├── ...
├── keyframes/
│   ├── L01_V001/
│   │   ├── 1234.jpg
│   │   ├── 5678.jpg
│   │   ├── ...
│   ├── ...
├── clip-features/
│   ├── L01_V001/
│   │   ├── 1234.npy
│   │   ├── 5678.npy
│   │   ├── ...
│   ├── ...
├── media-info/
│   ├── L01_V001.json
│   ├── ...
├── transcripts/
│   ├── L01_V001.json
│   ├── ...
├── ocr-json/
│   ├── L01_V001.json
│   ├── ...
```

- **videos**: contains all the videos provided by organizers, they are divided into batches and each batch contains multiple videos.
- **keyframes**: contains the keyframes extracted from the videos using [TransNet-V2](https://arxiv.org/abs/2008.04838).
- **clip-features**: contains the clip-level features extracted from the videos by using [ViT-L/14](https://huggingface.co/openai/clip-vit-large-patch14).
- **media-info**: contains the metadata of the videos provided by organizers.
- **transcripts**: contain the speech transcriptions extracted from the videos using Whisper.
- **ocr-json**: contain the optical character recognition (OCR) data extracted from video frames using EasyOCR


# Statistics
- Number of videos in each batch:
    - Batch 1: 873 videos, with 213323 vectors
    - Batch 2: 600 videos, with 420039 vectors
    - Batch 3: ... videos
