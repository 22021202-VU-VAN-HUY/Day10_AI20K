# Báo Cáo Nhóm - Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Điền trước khi nộp
**Thành viên:** Điền tên, vai trò và email trước khi nộp
**Ngày thực hiện:** 2026-06-10
**Run cuối:** `step5-restored-good`

## 1. Pipeline tổng quan

Nguồn ingest là `data/raw/policy_export_dirty.csv`, gồm 247 record từ năm
nguồn canonical cùng dữ liệu duplicate, legacy, invalid ID, thiếu field và
xung đột version. `etl_pipeline.py run` tạo `run_id`, đọc CSV, clean, ghi
cleaned/quarantine, chạy expectation và chỉ publish Chroma khi không có halt.
Sau publish, manifest ghi counts, watermark và thông tin collection; freshness
đọc manifest để kiểm tra SLA.

Lệnh chạy toàn bộ ingest → clean → validate → embed:

```powershell
.\.venv\Scripts\python.exe etl_pipeline.py run
```

Log cuối nằm tại `artifacts/logs/run_step5-restored-good.log`; manifest tương
ứng là `artifacts/manifests/manifest_step5-restored-good.json`.

## 2. Cleaning và expectation

Pipeline đọc allowlist và cutoff HR từ `contracts/data_contract.yaml`. Các
rule mở rộng gồm: validate ngày lịch thực; chuẩn hóa `exported_at`; phát hiện
HR stale bằng ngày lẫn marker nội dung; dọn prefix noise; deduplicate sau
transform; sửa biến thể refund 14 ngày; và tạo stable `chunk_id` không phụ
thuộc thứ tự CSV. `access_control_sop` được đăng ký làm nguồn canonical thứ
năm.

Các expectation mới kiểm tra registered source, đủ năm nguồn, không duplicate
sau transform, chunk ID unique và `exported_at` đúng ISO. Các lỗi này dùng
severity `halt` vì nếu bỏ qua sẽ tạo snapshot thiếu dữ liệu hoặc không
idempotent.

### Metric impact

| Rule / expectation | Trước | Sau / inject | Chứng cứ |
|---|---:|---:|---|
| Allowlist access control | 0 cleaned | 6 cleaned | cleaned CSV |
| HR stale content | 2 record lọt qua | 0; quarantine 8 | log và quarantine |
| Canonical coverage | 4/5 | 5/5 | `all_canonical_sources_present` |
| Refund expectation | pass ở run sạch | fail 1 violation khi inject | log inject |
| Duplicate sau transform | chưa kiểm | 0 | expectation log |
| Stable snapshot | ID phụ thuộc sequence | 34 vector, rerun không phình | Chroma + unit test |

## 3. Before/after retrieval

Kịch bản inject dùng `--no-refund-fix --skip-validate`, run
`step5-inject-bad-v2`. Expectation refund fail nhưng snapshot vẫn được embed
để tạo evidence. File `artifacts/eval/after_inject_bad.csv` cho thấy
`q_refund_window` có top-1 là nội dung 14 ngày và `hits_forbidden=yes`.
`grading_after_inject_bad.jsonl` vì vậy chỉ đạt 9/10 hoàn toàn.

Pipeline được chạy lại bình thường với run `step5-restored-good`. Publish đã
prune một stale ID rồi upsert 34 chunk sạch. File
`artifacts/eval/after_restore_good.csv` đạt 21/21:
`contains_expected=yes`, `hits_forbidden=no` và đúng top-1 source.
`artifacts/eval/grading_run.jsonl` đạt 10/10. Kết quả chứng minh data quality
có ảnh hưởng trực tiếp tới retrieval ngay cả khi keyword đúng vẫn xuất hiện ở
một chunk khác trong top-k.

## 4. Freshness và monitoring

Contract đặt SLA 24 giờ và alert channel `#data-observability`. PASS nghĩa là
watermark nằm trong SLA. WARN dành cho timestamp thiếu, sai hoặc nằm trong
tương lai, thường liên quan clock/producer. FAIL dành cho manifest thiếu/lỗi,
SLA không hợp lệ hoặc snapshot quá cũ.

Manifest cuối có `latest_exported_at=2026-04-10T00:00:00`, nên kiểm tra ngày
2026-06-10 trả FAIL `freshness_sla_exceeded`. Nhóm giữ kết quả này vì phản ánh
đúng tuổi của dữ liệu mẫu; không thay timestamp để tạo PASS giả.

## 5. Liên hệ Day 09

Collection mặc định là `day10_kb`, tách khỏi Day 09 để một run đang thử
nghiệm không ghi đè corpus agent. Khi cần tích hợp, Day 09 chỉ cần dùng cùng
`CHROMA_DB_PATH`, `CHROMA_COLLECTION` và embedding model. Chỉ manifest của run
đã pass expectation mới được xem là snapshot có thể phục vụ.

## 6. Rủi ro và peer review

- Lần tải SentenceTransformers đầu tiên cần mạng hoặc model cache.
- `--skip-validate` có thể publish dữ liệu xấu nếu dùng ngoài demo.
- Hybrid reranker cần quản trị alias khi thêm domain mới.
- Snapshot mẫu đang stale theo SLA.

Ba câu hỏi peer review:

1. Khi thêm một nguồn canonical mới, những file và expectation nào phải đổi?
2. Vì sao `contains_expected=true` vẫn chưa đủ để kết luận retrieval tốt?
3. Stable `chunk_id` và prune hỗ trợ rollback/rerun như thế nào?
