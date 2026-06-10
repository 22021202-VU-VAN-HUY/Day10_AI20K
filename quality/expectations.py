"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple

from transform.cleaning_rules import ALLOWED_DOC_IDS


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and re.search(
            r"\b14\s+ngày(?:\s+làm\s+việc)?\b",
            r.get("chunk_text") or "",
            re.IGNORECASE,
        )
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and re.search(
            r"\b10\s+ngày(?:\s+làm\s+việc)?\s+phép\s+năm\b",
            r.get("chunk_text") or "",
            re.IGNORECASE,
        )
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7: only registered sources may be published.
    unknown_docs = sorted(
        {
            (r.get("doc_id") or "").strip()
            for r in cleaned_rows
            if (r.get("doc_id") or "").strip() not in ALLOWED_DOC_IDS
        }
    )
    results.append(
        ExpectationResult(
            "only_registered_doc_ids",
            not unknown_docs,
            "halt",
            f"unknown_doc_ids={unknown_docs}",
        )
    )

    # E8: a complete snapshot contains every canonical source.
    present_docs = {(r.get("doc_id") or "").strip() for r in cleaned_rows}
    missing_docs = sorted(ALLOWED_DOC_IDS - present_docs)
    results.append(
        ExpectationResult(
            "all_canonical_sources_present",
            not missing_docs,
            "halt",
            f"missing_doc_ids={missing_docs}",
        )
    )

    # E9: transformations must not create duplicate published content.
    seen_content: set[Tuple[str, str]] = set()
    duplicate_content = 0
    for row in cleaned_rows:
        identity = (
            (row.get("doc_id") or "").strip(),
            " ".join((row.get("chunk_text") or "").strip().lower().split()),
        )
        if identity in seen_content:
            duplicate_content += 1
        seen_content.add(identity)
    results.append(
        ExpectationResult(
            "no_duplicate_doc_content",
            duplicate_content == 0,
            "halt",
            f"duplicate_rows={duplicate_content}",
        )
    )

    # E10: chunk_id is the idempotency key and must be non-empty and unique.
    chunk_ids = [(r.get("chunk_id") or "").strip() for r in cleaned_rows]
    duplicate_ids = len(chunk_ids) - len(set(chunk_ids))
    empty_ids = sum(not chunk_id for chunk_id in chunk_ids)
    results.append(
        ExpectationResult(
            "unique_non_empty_chunk_id",
            duplicate_ids == 0 and empty_ids == 0,
            "halt",
            f"duplicate_ids={duplicate_ids}, empty_ids={empty_ids}",
        )
    )

    # E11: exported_at follows the cleaned data contract.
    invalid_exported_at = 0
    for row in cleaned_rows:
        value = (row.get("exported_at") or "").strip()
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            valid = "T" in value
        except ValueError:
            valid = False
        invalid_exported_at += int(not valid)
    results.append(
        ExpectationResult(
            "exported_at_iso_datetime",
            invalid_exported_at == 0,
            "halt",
            f"invalid_exported_at_rows={invalid_exported_at}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
