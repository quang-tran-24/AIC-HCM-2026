import pandas as pd
import zipfile
import os
import subprocess

# Read the CSV file
csv_file_path = "batch1.csv"
dataframe = pd.read_csv(csv_file_path)

# Thư mục datasets/ nằm ở gốc project, script này chạy từ data_processing/stuff/
DATASETS_DIR = os.path.join("..", "..", "datasets")

download_dir = "downloads"
os.makedirs(download_dir, exist_ok=True)

# Mỗi loại file cần tải sẽ được giải nén vào đúng thư mục con tương ứng trong datasets/
# LƯU Ý: không tải "clip-features-32" vì đó là ViT-B/32 (512-dim), không khớp
#         với hệ thống đang dùng ViT-L/14 (768-dim) -> sẽ làm sai lệch khi search.
FILES_TO_DOWNLOAD = [
    {"pattern": r"map-keyframes-aic25-b1\.zip",  "extract_to": "map-keyframes"},
    {"pattern": r"media-info-aic25-b1\.zip",     "extract_to": "media-info"},
    {"pattern": r"objects-aic25-b1\.zip",        "extract_to": "objects"},
]

for item in FILES_TO_DOWNLOAD:
    matched_rows = dataframe[dataframe["Filenames"].str.match(item["pattern"], na=False)]
    extract_dir = os.path.join(DATASETS_DIR, item["extract_to"])
    os.makedirs(extract_dir, exist_ok=True)

    for _, row in matched_rows.iterrows():
        file_name = row["Filenames"]
        download_url = row["Download link"]
        local_zip_file_path = os.path.join(download_dir, file_name)

        print(f"Downloading: {file_name} from {download_url}")
        subprocess.run([
            "aria2c",
            "-x", "16",
            "-s", "16",
            "-o", file_name,
            "-d", download_dir,
            download_url
        ], check=True)

        print(f"Extracting: {file_name} -> {extract_dir}")
        with zipfile.ZipFile(local_zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

print("Completed downloading and extracting Keyframes/map-keyframes/media-info/objects for L21-L25 from batch1.")