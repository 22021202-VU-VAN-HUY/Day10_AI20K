# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Day10 AI20K
**Thành viên:**
| Tên | Vai trò (Day 10) | Mã học viên |
|-----|------------------|--------------|
| Kiệt | Ingestion / Raw Owner | Chưa cung cấp |
| Bảo | Cleaning & Quality Owner | Chưa cung cấp |
| Sỹ | Embed & Idempotency Owner | Chưa cung cấp |
| Huy | Monitoring / Freshness Owner | 2A202600750 |
| Kiên | Docs / Report Owner | Chưa cung cấp |

**Ngày nộp:** 2026-06-10
**Repo:** `Day10_AI20K`
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Pipeline `etl_pipeline.py run` thực hiện 4 bước: **Ingest** (load CSV raw 247 records) → **Clean** (apply cleaning rules: allowlist từ contract, date parse, HR stale, refund fix, dedupe, noise strip) → **Validate** (11 expectations, gồm halt và warn) → **Embed** (upsert 34 chunks vào Chroma collection `day10_kb`, prune ID thừa). Dữ liệu raw từ 5 hệ thống nguồn: policy_refund_v4, sla_p1_2026, it_helpdesk_faq, hr_leave_policy, access_control_sop. Run cuối `step5-restored-good` có 34 cleaned và 213 quarantine.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

```
python etl_pipeline.py run
```

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| **Rule: allowlist access_control_sop** | 8 record bị quarantine nhầm, 0 cleaned | 6 chunk hợp lệ vào cleaned | `cleaned_step5-restored-good.csv`; grading gq_d10_10 PASS |
| **Rule: HR content-based stale** | expectation HR FAIL, violations=2 | expectation OK; 8 record `stale_hr_policy_content` bị quarantine | Log baseline và quarantine run cuối |
| **Rule: normalize + dedupe sau transform** | Duplicate có thể phát sinh sau fix 14→7 | `no_duplicate_doc_content` OK, duplicate_rows=0 | `run_step5-restored-good.log` |
| **Expectation: all_canonical_sources_present** | Không kiểm coverage đủ nguồn | `missing_doc_ids=[]` | Log run cuối |
| **Expectation: exported_at_iso_datetime** | Không validate timestamp publish | `invalid_exported_at_rows=0` | Log run cuối |

**Rule chính (baseline + mở rộng):**

- **Mới 1:** allowlist và cutoff đọc từ `contracts/data_contract.yaml`, thêm `access_control_sop`.
- **Mới 2:** quarantine `hr_leave_policy` chứa marker bản cũ trong text, không chỉ check ngày.
- **Mới 3:** validate ngày lịch và `exported_at`, strip noise trước khi dedup.
- **Mới 4:** stable `chunk_id` theo source + nội dung, không phụ thuộc thứ tự CSV.

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

Pipeline baseline `2026-06-10T04-49Z`: `expectation[hr_leave_no_stale_10d_annual] FAIL (halt) :: violations=2`. Nguyên nhân: HR rows có effective_date ≥ 2026-01-01 nhưng text vẫn là "10 ngày phép năm (bản HR 2025)". Fix: thêm rule content-based; run `step5-restored-good` có violations=0.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Chạy pipeline với `--no-refund-fix --skip-validate` (run_id=`step5-inject-bad-v2`). Policy refund_v4 giữ nguyên "14 ngày làm việc". Expectation `refund_no_stale_14d_window` FAIL (violations=1) nhưng vẫn embed có chủ đích. Sau đó chạy lại pipeline chuẩn (run_id=`step5-restored-good`) để phục hồi dữ liệu sạch.

**Kết quả định lượng (từ CSV / bảng):**

| Metric | inject-bad (xấu) | after-fix (tốt) | Ghi chú |
|--------|-------------------|------------------|---------|
| `refund_no_stale_14d_window` | FAIL (violations=1) | OK (violations=0) | Stale refund window trong cleaned |
| `q_refund_window` hits_forbidden | **yes** | **no** | top-k chứa "14 ngày" → forbidden |
| `q_refund_window` contains_expected | yes | yes | Cả hai đều chứa "7 ngày" (nhiều chunk) |

**Bằng chứng:** `artifacts/eval/after_inject_bad.csv` và `artifacts/eval/after_restore_good.csv`. Dòng `q_refund_window` đổi từ `hits_forbidden=yes`, top-1 "14 ngày" sang `hits_forbidden=no`, top-1 "7 ngày". Cơ chế phát hiện: expectation kiểm cleaned rows; eval kiểm toàn bộ top-k retrieval.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

**SLA:** `FRESHNESS_SLA_HOURS=24` (pipeline phải chạy trong 24 giờ sau khi data export).
**Kết quả trên manifest mẫu:** `freshness_check=FAIL`. Lý do: `latest_exported_at=2026-04-10`, `age_hours=1469` — dữ liệu mẫu quá cũ so với SLA 24 giờ.
**Giải thích:** FAIL là hợp lý trên data mẫu. Khi dùng data thật, cần đảm bảo source export mới hoặc điều chỉnh `FRESHNESS_SLA_HOURS` phù hợp với tần suất update thực tế (ví dụ: policy PDF đổi 1 lần/tuần → SLA 168 giờ). Manifest ghi `run_id`, `run_timestamp`, `raw_records`, `cleaned_records`, `latest_exported_at` — dùng để trace freshness.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Collection `day10_kb` (34 chunks, 5 nguồn) có thể phục vụ retrieval worker trong Day 09. Supervisor query collection này để lấy context grounded cho LLM. Cùng domain CS + IT Helpdesk nên data docs trùng (`data/docs/`). Nếu Day 09 dùng collection riêng, cần embed lại bằng cùng pipeline.

---

## 6. Rủi ro còn lại & việc chưa làm

- **Retrieval ranking:** hybrid reranker đã cải thiện câu P1, nhưng alias domain cần quản trị khi thêm corpus mới.
- **Freshness SLA:** data mẫu luôn FAIL — cần adjust khi dùng data thật.
- **Source registration:** khi thêm nguồn mới phải đồng bộ data contract và source coverage expectation.
- **Chưa tích hợp Great Expectations thật** — dùng custom expectation suite.
- **Chưa có alert tự động** — chỉ log, chưa push notification khi expectation fail.
