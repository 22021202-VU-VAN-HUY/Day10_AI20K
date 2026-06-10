"""
Kiểm tra freshness từ manifest pipeline (SLA đơn giản theo giờ).

Sinh viên mở rộng: đọc watermark DB, so sánh với clock batch, v.v.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Tuple


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # Cho phép "2026-04-10T08:00:00" không có timezone
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def check_manifest_freshness(
    manifest_path: Path,
    *,
    sla_hours: float = 24.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).

    Đọc trường `latest_exported_at` hoặc max exported_at trong cleaned summary.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if sla_hours <= 0:
        return "FAIL", {"reason": "invalid_sla_hours", "sla_hours": sla_hours}
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}

    try:
        data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, JSONDecodeError) as exc:
        return "FAIL", {"reason": "invalid_manifest_json", "error": str(exc)}

    timestamp_field = "latest_exported_at"
    ts_raw = data.get(timestamp_field)
    if not ts_raw:
        timestamp_field = "run_timestamp"
        ts_raw = data.get(timestamp_field)
    dt = parse_iso(str(ts_raw)) if ts_raw else None
    if dt is None:
        reason = "invalid_timestamp_in_manifest" if ts_raw else "no_timestamp_in_manifest"
        return "WARN", {
            "reason": reason,
            "timestamp_field": timestamp_field,
            "timestamp_value": ts_raw,
        }

    age_hours = (now - dt).total_seconds() / 3600.0
    detail = {
        "timestamp_field": timestamp_field,
        "latest_exported_at": ts_raw,
        "age_hours": round(age_hours, 3),
        "sla_hours": sla_hours,
    }
    if age_hours < -(5 / 60):
        return "WARN", {**detail, "reason": "timestamp_in_future"}
    if age_hours <= sla_hours:
        return "PASS", detail
    return "FAIL", {**detail, "reason": "freshness_sla_exceeded"}
