"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover - requirements.txt installs PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "data_contract.yaml"

_DEFAULT_ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)
_DEFAULT_HR_MIN_EFFECTIVE_DATE = "2026-01-01"


def _load_contract_settings() -> Tuple[frozenset[str], str]:
    """Load source registration and version cutoff from the data contract."""
    if yaml is None or not CONTRACT_PATH.is_file():
        return _DEFAULT_ALLOWED_DOC_IDS, _DEFAULT_HR_MIN_EFFECTIVE_DATE
    try:
        contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8")) or {}
        allowed = frozenset(
            str(doc_id).strip()
            for doc_id in contract.get("allowed_doc_ids", [])
            if str(doc_id).strip()
        )
        versioning = contract.get("policy_versioning", {}) or {}
        hr_cutoff = str(
            versioning.get("hr_leave_min_effective_date", _DEFAULT_HR_MIN_EFFECTIVE_DATE)
        ).strip()
        return allowed or _DEFAULT_ALLOWED_DOC_IDS, hr_cutoff or _DEFAULT_HR_MIN_EFFECTIVE_DATE
    except (OSError, ValueError, TypeError):
        return _DEFAULT_ALLOWED_DOC_IDS, _DEFAULT_HR_MIN_EFFECTIVE_DATE


ALLOWED_DOC_IDS, HR_LEAVE_MIN_EFFECTIVE_DATE = _load_contract_settings()

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_STALE_REFUND_WINDOW = re.compile(r"\b14\s+ngày(?:\s+làm\s+việc)?\b", re.IGNORECASE)
_STALE_HR_ANNUAL_LEAVE = re.compile(
    r"\b10\s+ngày(?:\s+làm\s+việc)?\s+phép\s+năm\b",
    re.IGNORECASE,
)
_UNCLEAR_PREFIX = re.compile(r"^\s*nội dung không rõ ràng\s*:\s*", re.IGNORECASE)
_LEADING_NOISE = re.compile(r"^\s*!+\s*")
_REPEATED_WORKING_DAY = re.compile(
    r"\b(làm\s+việc)(?:\s+\1)+\b",
    re.IGNORECASE,
)


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int | None = None) -> str:
    """Return an ID that is stable across reruns and input row reordering."""
    identity = f"{doc_id}|{_norm_text(chunk_text)}"
    h = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return f"{doc_id}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        try:
            return date.fromisoformat(s).isoformat(), ""
        except ValueError:
            return "", "invalid_effective_date_value"
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        try:
            return date(int(yyyy), int(mm), int(dd)).isoformat(), ""
        except ValueError:
            return "", "invalid_effective_date_value"
    return "", "invalid_effective_date_format"


def _normalize_exported_at(raw: str) -> Tuple[str, str]:
    s = (raw or "").strip()
    if not s:
        return "", "missing_exported_at"

    candidate = s
    if re.match(r"^\d{4}/\d{2}/\d{2}T", candidate):
        candidate = candidate[:10].replace("/", "-") + candidate[10:]
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return "", "invalid_exported_at"
    if "T" not in candidate:
        return "", "invalid_exported_at"

    normalized = parsed.isoformat(timespec="seconds")
    if normalized.endswith("+00:00") and s.endswith("Z"):
        normalized = normalized[:-6] + "Z"
    return normalized, ""


def _clean_export_noise(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    cleaned = _UNCLEAR_PREFIX.sub("", cleaned)
    cleaned = _LEADING_NOISE.sub("", cleaned)
    cleaned = _REPEATED_WORKING_DAY.sub(r"\1", cleaned)
    return cleaned.strip()


def _contains_stale_hr_annual_leave(text: str) -> bool:
    normalized = _norm_text(text)
    return bool(
        _STALE_HR_ANNUAL_LEAVE.search(normalized)
        or "bản hr 2025" in normalized
    )


def _fix_refund_window(text: str) -> str:
    fixed, replacements = _STALE_REFUND_WINDOW.subn("7 ngày làm việc", text)
    if replacements:
        return fixed + " [cleaned: stale_refund_window]"
    return fixed


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Cleaning rules:
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Chuẩn hoá exported_at và quarantine timestamp không hợp lệ.
    4) Quarantine HR version cũ theo cutoff contract và marker nội dung.
    5) Dọn noise export, loại trùng sau transform và tạo chunk_id ổn định.
    6) Fix mọi biến thể cửa sổ refund 14 ngày thành policy hiện hành 7 ngày.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[Tuple[str, str]] = set()
    cleaned: List[Dict[str, Any]] = []

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = _clean_export_noise(raw.get("chunk_text", ""))
        eff_raw = raw.get("effective_date", "")
        exported_raw = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err:
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        exported_at, exported_err = _normalize_exported_at(exported_raw)
        if exported_err:
            quarantine.append({**raw, "reason": exported_err, "exported_at_raw": exported_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < HR_LEAVE_MIN_EFFECTIVE_DATE:
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        if doc_id == "hr_leave_policy" and _contains_stale_hr_annual_leave(text):
            quarantine.append({**raw, "reason": "stale_hr_policy_content"})
            continue

        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            fixed_text = _fix_refund_window(fixed_text)

        key = (doc_id, _norm_text(fixed_text))
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at,
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
