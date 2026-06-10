# Báo cáo triển khai phần 3 - Cleaning, Quality và Retrieval

**Ngày:** 2026-06-10  
**Run cuối:** `step3-final`

## 1. Mục tiêu thiết kế

Phần triển khai không đọc hoặc hard-code ID của 21 câu self-test hay 10 câu
grading. Các rule dựa trên data contract, schema và tính hợp lệ của nội dung để
có thể tiếp tục hoạt động khi bộ câu hỏi kiểm thử thay đổi.

## 2. Các thay đổi chính

### Cleaning rules

1. Đọc `allowed_doc_ids` và cutoff HR từ `contracts/data_contract.yaml`.
2. Đăng ký nguồn hợp lệ `access_control_sop`.
3. Validate ngày bằng parser lịch thực, không chỉ regex; ngày như
   `2026-02-30` bị quarantine.
4. Chuẩn hóa và validate `exported_at`, bao gồm biến thể dùng dấu `/`.
5. Phát hiện HR stale theo cả cutoff và marker nội dung `10 ngày phép năm`,
   kể cả khi record mang ngày năm 2026.
6. Sửa mọi biến thể cửa sổ refund `14 ngày` thành `7 ngày làm việc`.
7. Dọn prefix noise của export trước khi deduplicate.
8. Deduplicate sau transform theo `(doc_id, normalized_text)`.
9. Tạo `chunk_id` bằng hash của nguồn và nội dung, không phụ thuộc thứ tự CSV.

### Expectations mới

- `only_registered_doc_ids`
- `all_canonical_sources_present`
- `no_duplicate_doc_content`
- `unique_non_empty_chunk_id`
- `exported_at_iso_datetime`

Các expectation trên đều có severity `halt` vì vi phạm sẽ làm snapshot index
không đầy đủ, không idempotent hoặc sai contract.

### Retrieval

`retrieval.py` thực hiện hybrid retrieval:

1. Lấy tối thiểu 20 ứng viên từ vector search.
2. Rerank bằng độ phủ token Unicode.
3. Chuẩn hóa một số thuật ngữ Việt-Anh tổng quát như
   `update/cập nhật`, `escalate/chuyển cấp`, `refund/hoàn tiền`.

Reranker không sử dụng `must_contain_any`, `expect_top1_doc_id` hoặc ID câu hỏi.

## 3. Metric impact

| Rule / expectation | Trước | Sau |
|---|---:|---:|
| Nguồn `access_control_sop` trong cleaned | 0 | 6 |
| HR stale lọt qua expectation | 2 violations | 0 |
| Quarantine `stale_hr_policy_content` | 0 | 8 |
| Canonical sources hiện diện | 4/5 | 5/5 |
| Duplicate trong cleaned sau transform | Chưa kiểm soát | 0 |
| Invalid `exported_at` trong cleaned | Chưa kiểm tra | 0 |
| Self-test retrieval đạt đầy đủ | 18/21 ở lần kiểm tra đầu | 21/21 |
| Official grading đạt đầy đủ | 9/10 ở lần kiểm tra đầu | 10/10 |

Snapshot cuối:

| Chỉ số | Giá trị |
|---|---:|
| `raw_records` | 247 |
| `cleaned_records` | 34 |
| `quarantine_records` | 213 |
| Chroma upsert | 34 |
| Chroma stale IDs được prune | 2 |

## 4. Artifact và kiểm chứng

- Log: `artifacts/logs/run_step3-final.log`
- Cleaned: `artifacts/cleaned/cleaned_step3-final.csv`
- Quarantine: `artifacts/quarantine/quarantine_step3-final.csv`
- Manifest: `artifacts/manifests/manifest_step3-final.json`
- Self-test: `artifacts/eval/eval_after_fix.csv`
- Grading: `artifacts/eval/grading_run.jsonl`
- Unit tests: `10 passed`

Chế độ inject cũng được kiểm tra: khi
`apply_refund_window_fix=False`, expectation
`refund_no_stale_14d_window` fail với `violations=1` và pipeline phải halt nếu
không dùng `--skip-validate`.

## 5. Freshness

Run `step3-final` có `latest_exported_at=2026-04-10T00:00:00`, nên freshness
trả về `FAIL` với SLA 24 giờ tại thời điểm chạy ngày 2026-06-10. Đây là trạng
thái đúng của snapshot dữ liệu mẫu cũ, không phải lỗi cleaning hoặc embed.
