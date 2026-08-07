import json
import os
from glob import glob

DATASETS_DIR  = os.path.join("..", "..", "datasets")
MAP_KF_DIR    = os.path.join(DATASETS_DIR, "map-keyframes")
FPS_JSON_PATH = os.path.join(DATASETS_DIR, "fps.json")

csv_files = glob(os.path.join(MAP_KF_DIR, "*.csv"))
csv_files.sort()

# Load lại file cũ (nếu có) - dùng utf-8-sig để tự động bỏ qua BOM nếu có
fps_dictionary = {}
if os.path.exists(FPS_JSON_PATH):
    with open(FPS_JSON_PATH, "r", encoding="utf-8-sig") as f:
        fps_dictionary = json.load(f)

for csv_file in csv_files:
    base_name = os.path.splitext(os.path.basename(csv_file))[0]
    with open(csv_file, "r", encoding="utf-8-sig") as file:
        file.readline()  # skip header
        first_data_line = file.readline().strip().split(",")
        if len(first_data_line) >= 3:
            fps_dictionary[base_name] = float(first_data_line[2])

with open(FPS_JSON_PATH, "w", encoding="utf-8") as json_file:
    json.dump(fps_dictionary, json_file, indent=4, ensure_ascii=False)

print(f"[INFO] Updated {FPS_JSON_PATH} with {len(fps_dictionary)} videos")