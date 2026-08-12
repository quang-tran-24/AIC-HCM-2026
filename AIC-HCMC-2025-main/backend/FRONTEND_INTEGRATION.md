# Frontend 3 chế độ tìm kiếm + backend fixes đi kèm — integration guide

## Bối cảnh: 3 thay đổi liên quan, phải làm cùng nhau

Yêu cầu ban đầu ("tách UI thành 3 chế độ để Q&A không làm chậm query 1/3") kéo theo 3 việc:

1. **Fix thật cho vấn đề "chậm"**: `asyncio.to_thread` bọc quanh `run_qa_query`/`run_trake_query`
   trong 2 route — nếu không có cái này, tách UI vẫn không ngăn được việc 1 request Q&A
   đang chạy làm nghẽn toàn bộ event loop của uvicorn, kể cả với query khác tab/khác người.
2. **Fix 1 lỗ hổng phát hiện giữa chừng**: TRAKE dense-resample trước đây xóa hết ảnh sau khi
   tính điểm — không có gì để hiển thị. Giờ ảnh khung hình thắng cuộc được lưu vào
   `datasets/keyframes_dense/<video>/<frame_id>.jpg`.
3. **UI 3 chế độ thật** trong `SearchView.vue` + `retrieval.js` + `ContentView.vue`.

## File đã sửa/thêm trong đợt này

```
backend/api/qa_search.py       sửa — asyncio.to_thread, trả thêm keyframe_path
backend/api/trake_search.py    sửa — asyncio.to_thread, trả thêm frame_paths
backend/trake_alignment.py     sửa — lưu ảnh dense-refine thắng cuộc xuống đĩa
backend/qa_answer.py           sửa — trả thêm keyframe_path (ảnh thật, đúng tên file)
frontend/src/api/retrieval.js  sửa — thêm API.qaSearch(), API.trakeSearch()
frontend/src/components/SearchView.vue    sửa — 3 tab chế độ (KIS / Q&A / TRAKE)
frontend/src/components/ContentView.vue   sửa — hiện được số frame/nhãn event khi không có link youtube
```

## Cần thêm 1 route static-file MỚI trong `backend/main.py`

Ảnh QA dùng lại đúng `keyframe_path` đã có sẵn (tĩnh, đã copy thủ công vào
`frontend/src/assets/...` như quy trình cũ) — không cần gì thêm.

Nhưng ảnh TRAKE (`datasets/keyframes_dense/...`) được **sinh động mỗi lần search** — không
thể áp dụng quy trình "copy tay 1 lần" cho dữ liệu tĩnh được. Cần mount 1 route serve file
tĩnh để frontend load thẳng qua HTTP:

```python
# backend/main.py
from fastapi.staticfiles import StaticFiles
import os

os.makedirs(os.path.join("datasets", "keyframes_dense"), exist_ok=True)
app.mount("/dense-frames", StaticFiles(directory=os.path.join("datasets", "keyframes_dense")), name="dense_frames")
```

Đặt sau `app = FastAPI()` và trước (hoặc sau, không quan trọng thứ tự) các `app.include_router(...)`.
Frontend sẽ load ảnh TRAKE qua `http://<IP>/dense-frames/<video>/<frame_id>.jpg` — không qua
`src/assets/...` như các ảnh KIS/Q&A khác.

## Các thay đổi khác cần làm ở `backend/main.py` (gộp từ các đợt trước, nếu chưa làm)

- `app.state.qwen_vl_answerer = QwenVLAnswerer()` lúc startup (xem `QA_INTEGRATION.md`)
- Fix `app.state.milvus_scene` chưa init (xem `INTEGRATION.md`)
- `app.include_router(qa_search.router)`, `app.include_router(trake_search.router)`

## Cách hoạt động của UI mới

3 nút tab ở đầu sidebar (`Query 1 · KIS` / `Query 2 · Q&A` / `Query 3 · TRAKE`):

- **KIS**: y hệt giao diện cũ (Base query + Transcription + OCR + các nút Search),
  không đổi gì cả — chỉ ẩn/hiện bằng `v-show` chứ không xóa, tránh đụng logic cũ.
- **Q&A**: 1 textarea dán nguyên văn truy vấn (context + câu hỏi), 1 ô số "Số frame ngữ
  cảnh" (mặc định 1, tăng lên nếu Qwen trả lời sai do cảnh chuyển động nhanh — đúng cờ
  `num_context_frames` đã có ở backend). Kết quả hiện lại đúng khung hiển thị cũ
  (1 video, 1 frame) kèm câu hỏi + câu trả lời ở dòng text bên dưới.
- **TRAKE**: 1 textarea dán nguyên văn truy vấn (context + `E1:`.."En:"). Kết quả hiện 1
  video với N frame theo đúng thứ tự sự kiện, mỗi frame có nhãn `E1`, `E2`... đè lên số
  frame để dễ đối chiếu.

Cả 2 chế độ mới đều **tái dùng nguyên `ContentView.vue`** bằng cách đóng gói kết quả trả về
đúng hình dạng dữ liệu `{title, frames, text}` mà nó vốn đã hiểu — không viết component
hiển thị mới, giảm rủi ro breaking UI hiện có.

Phần "Question ID / QA checkbox (submit DRES) / Manual input / nút Submit" ở dưới **luôn
hiển thị bất kể đang ở chế độ nào** — vì đó là bước chọn frame để nộp bài, độc lập với việc
đang tìm kiếm theo kiểu nào. Lưu ý: checkbox "QA" đó là của flow submit DRES cũ, KHÔNG phải
module Q&A mới — 2 thứ trùng tên nhưng khác chức năng hoàn toàn, không đụng vào nhau.

## Đã build thử thật

Chạy `npm install && npm run build` trên bản đã sửa — build sạch, không lỗi mới (lỗi lint
`TemporalSearch is defined but never used` là có sẵn từ code gốc, không liên quan đợt này).
