# Data contract - Lab Day 10

Contract máy đọc nằm tại `contracts/data_contract.yaml`. Tài liệu này mô tả
ý nghĩa vận hành và quyền sở hữu.

## 1. Nguồn dữ liệu

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|---|---|---|---|
| `policy_refund_v4` | CSV export từ policy system | Chunk stale 14 ngày, duplicate, thiếu ngày | `refund_no_stale_14d_window`, quarantine reason |
| `sla_p1_2026` | CSV export từ support system | Duplicate, thiếu text/date, lẫn P1/P2 | volume theo `doc_id`, source coverage |
| `it_helpdesk_faq` | CSV export từ knowledge base | Duplicate, text noise, thiếu field | duplicate count, schema expectations |
| `hr_leave_policy` | CSV export từ HR system | Bản 2025 lẫn bản 2026, 10/12 ngày phép | cutoff contract, `stale_hr_policy_content` |
| `access_control_sop` | CSV export từ IT Security | Nguồn hợp lệ bị thiếu allowlist | `all_canonical_sources_present` |

Owner mặc định là `Day10 Data Platform Team`. Alert được gửi tới
`#data-observability`. Các `invalid_doc_*`, `legacy_catalog_xyz_zzz`,
`security_policy` và `data_privacy_guideline` không thuộc snapshot canonical
của lab này.

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| `chunk_id` | string | Có | Unique, non-empty, hash ổn định của source + nội dung |
| `doc_id` | string | Có | Thuộc `allowed_doc_ids` trong YAML |
| `chunk_text` | string | Có | Tối thiểu 8 ký tự, không stale, không duplicate |
| `effective_date` | date | Có | Ngày lịch hợp lệ dạng `YYYY-MM-DD` |
| `exported_at` | datetime | Có | ISO datetime hợp lệ, slash date được chuẩn hóa |

## 3. Quarantine và phục hồi

Record không đạt contract không bị xóa im lặng. Pipeline ghi nguyên record kèm
`reason` vào `artifacts/quarantine/quarantine_<run-id>.csv`. Các reason chính:

- `unknown_doc_id`
- `missing_chunk_text`, `missing_effective_date`
- `invalid_effective_date_format`, `invalid_effective_date_value`
- `invalid_exported_at`
- `duplicate_chunk_text`
- `stale_hr_policy_effective_date`, `stale_hr_policy_content`

Cleaning/Quality Owner xác nhận nguyên nhân. Nếu nguồn hợp lệ mới cần được
thêm, phải cập nhật cả YAML, tài liệu source map và expectation coverage trước
khi rerun. Không sửa trực tiếp cleaned CSV hoặc Chroma.

## 4. Phiên bản canonical

| `doc_id` | Source of truth | Phiên bản/cutoff |
|---|---|---|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | v4, cửa sổ 7 ngày |
| `sla_p1_2026` | `data/docs/sla_p1_2026.txt` | 2026 |
| `it_helpdesk_faq` | `data/docs/it_helpdesk_faq.txt` | FAQ hiện hành |
| `hr_leave_policy` | `data/docs/hr_leave_policy.txt` | cutoff `2026-01-01` từ YAML |
| `access_control_sop` | `data/docs/access_control_sop.txt` | effective `2026-01-01` |

Cutoff HR được đọc từ contract thay vì hard-code trong cleaning. Marker nội
dung bản cũ vẫn bị quarantine để bắt record mang ngày mới nhưng nội dung stale.
