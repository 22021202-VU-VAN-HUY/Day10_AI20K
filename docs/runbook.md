# Runbook - Lab Day 10

## Symptom

- Agent trả lời cửa sổ hoàn tiền là 14 ngày thay vì 7 ngày.
- Câu HR trả lời 10 ngày phép năm thay vì 12 ngày.
- Câu access control không tìm thấy `access_control_sop`.
- Pipeline ghi `PIPELINE_HALT`, collection thiếu nguồn hoặc freshness FAIL.
- Eval có `contains_expected=no`, `hits_forbidden=yes` hoặc sai top-1.

## Detection

1. Kiểm tra exit code và các dòng `expectation[...]` trong log.
2. So sánh `raw_records`, `cleaned_records`, `quarantine_records`.
3. Kiểm tra `artifacts/eval/*.csv` và grading JSONL.
4. Chạy freshness trên manifest của run vừa publish.

```powershell
.\.venv\Scripts\python.exe etl_pipeline.py freshness `
  --manifest artifacts\manifests\manifest_step5-restored-good.json
```

### Ý nghĩa freshness

| Trạng thái | Ý nghĩa | Hành động |
|---|---|---|
| PASS | Watermark không quá SLA 24 giờ | Tiếp tục phục vụ |
| WARN | Thiếu/sai timestamp hoặc timestamp ở tương lai | Kiểm tra clock và producer |
| FAIL | Manifest thiếu/lỗi, SLA không hợp lệ hoặc snapshot quá cũ | Cảnh báo owner, không coi dữ liệu là fresh |

Snapshot mẫu có `latest_exported_at=2026-04-10T00:00:00`; run ngày
2026-06-10 vì vậy FAIL với `freshness_sla_exceeded`. Đây là dữ liệu mẫu cũ,
không phải lỗi embed.

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|---|---|---|
| 1 | Mở manifest mới nhất | Có `run_id`, counts, watermark, collection |
| 2 | Đọc log cùng `run_id` | Xác định expectation fail hoặc publish thành công |
| 3 | Group quarantine theo `reason` | Thấy nguồn/field/version gây lỗi |
| 4 | Đối chiếu `contracts/data_contract.yaml` | Source và cutoff đúng contract |
| 5 | Chạy eval và grading | Xác định câu, forbidden text và top-1 sai |
| 6 | Kiểm tra collection count | Bằng cleaned count, không có stale ID |

Thứ tự debug: freshness/version → volume/errors → schema/contract →
lineage/run_id → retrieval/model.

## Mitigation

1. Không dùng `--skip-validate` trong production.
2. Sửa source hoặc cleaning rule; không sửa trực tiếp vector database.
3. Chạy lại pipeline chuẩn:

```powershell
.\.venv\Scripts\python.exe etl_pipeline.py run --run-id recovery-good
.\.venv\Scripts\python.exe eval_retrieval.py --out artifacts\eval\recovery.csv
.\.venv\Scripts\python.exe grading_run.py --out artifacts\eval\grading_run.jsonl
```

4. Xác nhận `PIPELINE_OK`, mọi halt expectation pass và quick-check exit 0.
5. Nếu chưa thể phục hồi, gắn trạng thái “data stale” và giữ snapshot tốt gần
nhất; không publish một run đang halt.

## Prevention

- Duy trì allowlist và cutoff trong data contract.
- Bắt stale content theo nội dung, không chỉ dựa vào ngày.
- Upsert theo stable `chunk_id` và prune ID ngoài snapshot.
- Chạy unit tests, self-test và grading trước khi publish release.
- Alert khi freshness FAIL hoặc canonical source bị thiếu.
- Chỉ cho phép `--skip-validate` trong kịch bản inject có `run_id` rõ ràng.
