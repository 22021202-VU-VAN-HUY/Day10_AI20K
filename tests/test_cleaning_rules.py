from __future__ import annotations

from copy import deepcopy

from quality.expectations import run_expectations
from transform.cleaning_rules import ALLOWED_DOC_IDS, clean_rows


def _row(
    doc_id: str,
    text: str,
    *,
    effective_date: str = "2026-01-01",
    exported_at: str = "2026-04-10T00:00:00",
) -> dict[str, str]:
    return {
        "chunk_id": "raw-id",
        "doc_id": doc_id,
        "chunk_text": text,
        "effective_date": effective_date,
        "exported_at": exported_at,
    }


def test_access_control_is_registered() -> None:
    assert "access_control_sop" in ALLOWED_DOC_IDS


def test_stale_hr_content_is_rejected_even_with_new_date() -> None:
    cleaned, quarantine = clean_rows(
        [
            _row(
                "hr_leave_policy",
                "Nhân viên dưới 3 năm được 10 ngày phép năm (bản HR 2025).",
                effective_date="2026-03-01",
            )
        ]
    )

    assert cleaned == []
    assert quarantine[0]["reason"] == "stale_hr_policy_content"


def test_sick_leave_ten_days_is_not_mistaken_for_stale_annual_leave() -> None:
    cleaned, quarantine = clean_rows(
        [_row("hr_leave_policy", "Nghỉ ốm: 10 ngày/năm có trả lương.")]
    )

    assert len(cleaned) == 1
    assert quarantine == []


def test_refund_variants_are_fixed_before_deduplication() -> None:
    rows = [
        _row("policy_refund_v4", "Yêu cầu trong vòng 14 ngày."),
        _row("policy_refund_v4", "Nội dung không rõ ràng: !!!Yêu cầu trong vòng 14 ngày."),
    ]

    cleaned, quarantine = clean_rows(rows)

    assert len(cleaned) == 1
    assert "7 ngày làm việc" in cleaned[0]["chunk_text"]
    assert quarantine[0]["reason"] == "duplicate_chunk_text"


def test_export_noise_cleanup_preserves_email_addresses() -> None:
    cleaned, quarantine = clean_rows(
        [
            _row(
                "policy_refund_v4",
                "Nội dung không rõ ràng: !!!Email: cs-refund@company.internal.",
            )
        ]
    )

    assert quarantine == []
    assert "cs-refund@company.internal" in cleaned[0]["chunk_text"]


def test_chunk_ids_do_not_depend_on_input_order() -> None:
    rows = [
        _row("policy_refund_v4", "Chính sách hoàn tiền hiện hành."),
        _row("sla_p1_2026", "Ticket P1 phản hồi trong 15 phút."),
    ]
    reversed_rows = list(reversed(deepcopy(rows)))

    first, _ = clean_rows(rows)
    second, _ = clean_rows(reversed_rows)

    first_ids = {row["chunk_text"]: row["chunk_id"] for row in first}
    second_ids = {row["chunk_text"]: row["chunk_id"] for row in second}
    assert first_ids == second_ids


def test_invalid_calendar_date_and_timestamp_are_quarantined() -> None:
    _, bad_date = clean_rows(
        [_row("policy_refund_v4", "Valid text here.", effective_date="2026-02-30")]
    )
    _, bad_timestamp = clean_rows(
        [_row("policy_refund_v4", "Another valid text.", exported_at="not-a-time")]
    )

    assert bad_date[0]["reason"] == "invalid_effective_date_value"
    assert bad_timestamp[0]["reason"] == "invalid_exported_at"


def test_expectations_detect_missing_sources_duplicates_and_bad_timestamp() -> None:
    row = {
        "chunk_id": "same-id",
        "doc_id": "policy_refund_v4",
        "chunk_text": "A valid refund policy chunk.",
        "effective_date": "2026-01-01",
        "exported_at": "bad-time",
    }
    results, halt = run_expectations([row, deepcopy(row)])
    by_name = {result.name: result for result in results}

    assert halt is True
    assert by_name["all_canonical_sources_present"].passed is False
    assert by_name["no_duplicate_doc_content"].passed is False
    assert by_name["unique_non_empty_chunk_id"].passed is False
    assert by_name["exported_at_iso_datetime"].passed is False
