# Raw Data Analysis - Step 2.2

Ngay phan tich: 2026-06-10

## 1. Pham vi phan tich

Da doi chieu cac file:

- `data/raw/policy_export_dirty.csv`
- `transform/cleaning_rules.py`
- `data/grading_questions.json`
- `artifacts/logs/run_2026-06-10T04-49Z.log`
- `artifacts/cleaned/cleaned_2026-06-10T04-49Z.csv`
- `artifacts/quarantine/quarantine_2026-06-10T04-49Z.csv`

## 2. Tong quan raw data

| Chi so | Gia tri |
|---|---:|
| Tong so record | 247 |
| So `doc_id` unique | 39 |
| Record rong `doc_id` | 0 |
| Record rong `chunk_text` | 20 |
| Record rong `effective_date` | 9 |
| Ngay theo dinh dang `DD/MM/YYYY` | 19 |
| Ngay sai dinh dang khac | 0 |

Raw data gom 5 nguon nghiep vu hop le, cac nguon ngoai pham vi, mot
legacy catalog va nhieu `invalid_doc_*`.

## 3. Nam nguon hop le can duoc ingest

| `doc_id` | Raw records | So cau grading yeu cau | Trang thai baseline |
|---|---:|---:|---|
| `policy_refund_v4` | 33 | 3 | Co trong allowlist |
| `sla_p1_2026` | 31 | 3 | Co trong allowlist |
| `it_helpdesk_faq` | 26 | 2 | Co trong allowlist |
| `hr_leave_policy` | 40 | 1 | Co trong allowlist |
| `access_control_sop` | 8 | 1 | **Thieu trong allowlist** |

`ALLOWED_DOC_IDS` hien chi co 4 nguon dau tien. Trong khi do,
`gq_d10_10` yeu cau top-1 retrieval la `access_control_sop`.

Ket luan: `access_control_sop` la nguon hop le dang bi quarantine nham.
Can them nguon nay vao `ALLOWED_DOC_IDS`.

## 4. Cac `doc_id` khong nen dua vao index

| Nhom | So record | Ly do |
|---|---:|---|
| `data_privacy_guideline` | 29 | Khong co trong 5 tai lieu cua lab va khong duoc grading yeu cau |
| `security_policy` | 18 | Khong co trong 5 tai lieu cua lab va khong duoc grading yeu cau |
| `legacy_catalog_xyz_zzz` | 31 | Du lieu legacy |
| 31 `invalid_doc_*` | 31 | Export loi/ID rac, moi ID co 1 record |

Khong nen mo rong allowlist cho cac nguon tren chi de giam so record
quarantine. Quarantine cac record nay la dung hanh vi mong doi.

## 5. Ket qua pipeline baseline

Theo log `run_2026-06-10T04-49Z.log`:

| Chi so | Gia tri |
|---|---:|
| Raw records | 247 |
| Cleaned records | 40 |
| Quarantine records | 207 |
| Ket qua | `PIPELINE_HALT` |

Cleaned records theo nguon:

| `doc_id` | Cleaned records |
|---|---:|
| `policy_refund_v4` | 14 |
| `sla_p1_2026` | 7 |
| `it_helpdesk_faq` | 10 |
| `hr_leave_policy` | 9 |
| `access_control_sop` | 0 |

Quarantine theo ly do:

| Ly do | So record |
|---|---:|
| `unknown_doc_id` | 117 |
| `duplicate_chunk_text` | 55 |
| `stale_hr_policy_effective_date` | 22 |
| `missing_chunk_text` | 7 |
| `missing_effective_date` | 6 |

Trong 117 record `unknown_doc_id`, co 8 record cua
`access_control_sop` dang bi quarantine nham.

## 6. Nguyen nhan pipeline HALT

Expectation bi fail:

```text
expectation[hr_leave_no_stale_10d_annual] FAIL (halt) :: violations=2
```

Cleaning rule HR hien chi loai record co:

```text
doc_id == "hr_leave_policy" and effective_date < "2026-01-01"
```

Rule nay chua du vi raw data van co noi dung cua ban HR 2025
(`10 ngay phep nam`) nhung mang `effective_date` nam 2026. Hai record
nhu vay da vuot qua cleaning va lam expectation fail.

Vi vay, du lieu stale can duoc nhan dien bang ca noi dung/version marker,
khong chi dua vao `effective_date`.

## 7. Cac van de du lieu da xac dinh

1. `access_control_sop` hop le nhung thieu trong allowlist.
2. Co 55 duplicate theo noi dung sau khi chuan hoa.
3. Co 20 record thieu `chunk_text`.
4. Co 9 record thieu `effective_date`.
5. Co 19 ngay dang `DD/MM/YYYY`, can chuan hoa sang ISO.
6. Co chunk refund stale ghi `14 ngay lam viec`, trong khi grading yeu cau 7 ngay.
7. Co chunk HR stale ghi `10 ngay phep nam`, trong khi ban 2026 la 12 ngay.
8. Loc stale HR theo ngay khong du de phat hien record mang noi dung cu
   nhung ngay export/effective moi.
9. Cac nguon legacy, invalid va ngoai pham vi khong duoc embed.

## 8. Dau vao cho buoc sua code

Buoc tiep theo trong `transform/cleaning_rules.py`:

1. Them `access_control_sop` vao `ALLOWED_DOC_IDS`.
2. Quarantine moi chunk HR chua marker `10 ngay phep nam`, ke ca khi
   `effective_date` tu nam 2026.
3. Giu viec chuan hoa `DD/MM/YYYY` sang `YYYY-MM-DD`.
4. Giu quarantine cho missing text, missing date, duplicate va unknown ID.
5. Kiem tra rule refund xu ly tat ca bien the noi dung stale 14 ngay.

Buoc tiep theo trong `quality/expectations.py`:

1. Them expectation bao dam du ca 5 `doc_id` hop le sau cleaning.
2. Them expectation bao dam khong con duplicate `chunk_text`.
3. Co the them expectation bao dam khong co `doc_id` ngoai allowlist.

Sau khi sua, pipeline can exit 0 va `access_control_sop` phai xuat hien
trong cleaned/index de cau `gq_d10_10` co the pass.
