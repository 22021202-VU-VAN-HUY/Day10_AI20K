# Quality report - Lab Day 10

**Run xấu:** `step5-inject-bad-v2`  
**Run phục hồi:** `step5-restored-good`  
**Ngày:** 2026-06-10

## 1. Tóm tắt số liệu

| Chỉ số | Inject xấu | Sau phục hồi |
|---|---:|---:|
| `raw_records` | 247 | 247 |
| `cleaned_records` | 34 | 34 |
| `quarantine_records` | 213 | 213 |
| Refund expectation | FAIL, 1 violation | PASS, 0 violation |
| Validation | Bị bỏ qua có chủ đích | Tất cả pass |
| Vector được prune | 1 | 1 |

Số lượng record không đổi vì corruption nằm trong nội dung của một chunk.
Expectation và retrieval evidence mới là tín hiệu phân biệt chất lượng.

## 2. Before/after retrieval

Artifact:

- Xấu: `artifacts/eval/after_inject_bad.csv`
- Tốt: `artifacts/eval/after_restore_good.csv`
- Grading xấu: `artifacts/eval/grading_after_inject_bad.jsonl`
- Grading cuối: `artifacts/eval/grading_run.jsonl`

| Kết quả | Inject xấu | Sau phục hồi |
|---|---:|---:|
| Self-test `contains_expected=yes` | 21/21 | 21/21 |
| Self-test `hits_forbidden=yes` | 1/21 | 0/21 |
| Self-test đúng top-1 source | 21/21 | 21/21 |
| Grading pass đầy đủ | 9/10 | 10/10 |

Ở `q_refund_window`, snapshot xấu trả top-1:

```text
Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc...
```

Kết quả có `contains_expected=yes` nhưng đồng thời `hits_forbidden=yes`. Điều
này chứng minh chỉ kiểm tra keyword đúng là chưa đủ; toàn bộ top-k phải không
chứa policy stale. Sau phục hồi, câu này có `hits_forbidden=no`.

## 3. Corruption inject

Lệnh inject:

```powershell
.\.venv\Scripts\python.exe etl_pipeline.py run `
  --run-id step5-inject-bad-v2 --no-refund-fix --skip-validate
```

`refund_no_stale_14d_window` fail với `violations=1`. Cờ
`--skip-validate` cho phép publish có chủ đích để đo tác động. Pipeline chuẩn
sau đó prune stale ID và upsert snapshot sạch.

## 4. Freshness

SLA là 24 giờ theo contract. Manifest phục hồi có watermark
`2026-04-10T00:00:00`, nên freshness FAIL khi chạy ngày 2026-06-10. Trạng thái
này được giữ nguyên làm bằng chứng monitoring thay vì sửa timestamp dữ liệu.

## 5. Hạn chế

- Eval hiện dùng retrieval + keyword, chưa có LLM judge.
- Snapshot mẫu không thể đạt freshness PASS nếu không có export mới.
- Alias của hybrid retrieval cần quản trị theo domain khi thêm corpus mới.
