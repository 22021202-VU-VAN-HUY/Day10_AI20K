from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from monitoring.freshness_check import check_manifest_freshness


NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _manifest(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_freshness_passes_within_sla(tmp_path: Path) -> None:
    path = _manifest(tmp_path, {"latest_exported_at": "2026-06-10T06:00:00+00:00"})
    status, detail = check_manifest_freshness(path, sla_hours=24, now=NOW)

    assert status == "PASS"
    assert detail["age_hours"] == 6.0


def test_freshness_fails_when_snapshot_is_stale(tmp_path: Path) -> None:
    path = _manifest(tmp_path, {"latest_exported_at": "2026-06-08T00:00:00+00:00"})
    status, detail = check_manifest_freshness(path, sla_hours=24, now=NOW)

    assert status == "FAIL"
    assert detail["reason"] == "freshness_sla_exceeded"


def test_freshness_warns_for_missing_or_future_timestamp(tmp_path: Path) -> None:
    missing = _manifest(tmp_path, {"run_id": "missing-time"})
    status_missing, detail_missing = check_manifest_freshness(
        missing, sla_hours=24, now=NOW
    )
    future = _manifest(
        tmp_path,
        {"latest_exported_at": "2026-06-10T14:00:00+00:00"},
    )
    status_future, detail_future = check_manifest_freshness(
        future, sla_hours=24, now=NOW
    )

    assert status_missing == "WARN"
    assert detail_missing["reason"] == "no_timestamp_in_manifest"
    assert status_future == "WARN"
    assert detail_future["reason"] == "timestamp_in_future"


def test_freshness_handles_invalid_manifest_and_sla(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")

    status_json, detail_json = check_manifest_freshness(invalid, now=NOW)
    status_sla, detail_sla = check_manifest_freshness(
        invalid, sla_hours=0, now=NOW
    )

    assert status_json == "FAIL"
    assert detail_json["reason"] == "invalid_manifest_json"
    assert status_sla == "FAIL"
    assert detail_sla["reason"] == "invalid_sla_hours"
