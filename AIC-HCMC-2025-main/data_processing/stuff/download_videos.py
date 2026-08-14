import pandas as pd
import zipfile
import os
import subprocess

# Read the CSV file
csv_file_path = "batch1.csv"
dataframe = pd.read_csv(csv_file_path)

# Thư mục datasets/ nằm ở gốc project, script này chạy từ data_processing/stuff/
DATASETS_DIR = os.path.join("..", "..", "datasets")

# Mỗi loại file cần tải sẽ được giải nén vào đúng thư mục con tương ứng trong datasets/
# LƯU Ý: không tải "clip-features-32" vì đó là ViT-B/32 (512-dim), không khớp
#         với hệ thống đang dùng ViT-L/14 (768-dim) -> sẽ làm sai lệch khi search.
FILES_TO_DOWNLOAD = [
    {
        "pattern": r"Keyframes_.*\.zip",
        "download_to": "keyframes"
    },
    {
        "pattern": r"Videos_L.*\.zip",
        "download_to": "videos"
    },
]

base_download_dir = "downloads"
os.makedirs(base_download_dir, exist_ok=True)

for item in FILES_TO_DOWNLOAD:

    download_dir = os.path.join(
        base_download_dir,
        item["download_to"]
    )

    os.makedirs(download_dir, exist_ok=True)

    matched_rows = dataframe[
        dataframe["Filenames"].str.match(
            item["pattern"],
            na=False
        )
    ]

    for _, row in matched_rows.iterrows():

        file_name = row["Filenames"]
        download_url = row["Download link"]

        local_file_path = os.path.join(download_dir, file_name)

        if os.path.exists(local_file_path):
            print(f"Skipping: {file_name} (already downloaded)")
            continue

        print(f"Downloading: {file_name}")
        print(f"Saving to: {download_dir}")

        subprocess.run([
            "aria2c",
            "-x", "16",
            "-s", "16",
            "-o", file_name,
            "-d", download_dir,
            download_url
        ], check=True)

        # print(f"Extracting: {file_name} -> {extract_dir}")
        # with zipfile.ZipFile(local_zip_file_path, 'r') as zip_ref:
        #     zip_ref.extractall(extract_dir)

print("Completed downloading and extracting from batch1.")