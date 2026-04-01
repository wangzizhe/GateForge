from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_9_manifests"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_9_manifests"
MAINLINE_MANIFEST_VERSION = "v0_3_9_mainline_manifest_v1"
CONTRAST_MANIFEST_VERSION = "v0_3_9_absorbed_success_contrast_manifest_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _task_id(row: dict) -> str:
    return str(row.get("task_id") or row.get("mutation_id") or "").strip()


def build_v0_3_9_manifests(
    *,
    refreshed_summary_path: str,
    lane_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    lane = _load_json(lane_summary_path)
    rows = _task_rows(refreshed)

    mainline_rows = [dict(row) for row in rows]
    contrast_rows = []
    explicit_subset_ids = []

    for row in rows:
        if row.get("success_after_branch_switch") is True:
            explicit_subset_ids.append(_task_id(row))
        if bool(row.get("success_without_branch_switch_evidence")):
            contrast_rows.append(
                {
                    **row,
                    "source_mainline_task_id": _task_id(row),
                    "movement_reason": "absorbed_success_in_v0_3_8_live_refresh",
                    "contrast_entry_rule": "success_without_branch_switch_evidence_true",
                }
            )

    mainline_manifest = {
        "schema_version": MAINLINE_MANIFEST_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if mainline_rows else "EMPTY",
        "manifest_role": "mainline",
        "source_refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "source_lane_summary_path": str(Path(lane_summary_path).resolve()) if Path(lane_summary_path).exists() else str(lane_summary_path),
        "lane_status": str((lane or {}).get("lane_status") or ""),
        "task_count": len(mainline_rows),
        "task_ids": [_task_id(row) for row in mainline_rows if _task_id(row)],
        "explicit_branch_switch_subset_task_ids": explicit_subset_ids,
        "tasks": mainline_rows,
    }
    contrast_manifest = {
        "schema_version": CONTRAST_MANIFEST_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if contrast_rows else "EMPTY",
        "manifest_role": "contrast_absorbed_success",
        "source_refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "task_count": len(contrast_rows),
        "task_ids": [_task_id(row) for row in contrast_rows if _task_id(row)],
        "tasks": contrast_rows,
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if mainline_rows else "EMPTY",
        "source_refreshed_summary_path": mainline_manifest["source_refreshed_summary_path"],
        "source_lane_summary_path": mainline_manifest["source_lane_summary_path"],
        "metrics": {
            "mainline_task_count": len(mainline_rows),
            "contrast_task_count": len(contrast_rows),
            "explicit_branch_switch_subset_count": len(explicit_subset_ids),
            "lane_status": mainline_manifest["lane_status"],
        },
    }

    out_root = Path(out_dir)
    _write_json(out_root / "mainline_manifest.json", mainline_manifest)
    _write_json(out_root / "contrast_manifest.json", contrast_manifest)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.9 Manifests",
                "",
                f"- status: `{summary['status']}`",
                f"- mainline_task_count: `{summary['metrics']['mainline_task_count']}`",
                f"- contrast_task_count: `{summary['metrics']['contrast_task_count']}`",
                f"- explicit_branch_switch_subset_count: `{summary['metrics']['explicit_branch_switch_subset_count']}`",
                "",
            ]
        ),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build frozen v0.3.9 mainline and contrast manifests from v0.3.8 live evidence.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_9_manifests(
        refreshed_summary_path=str(args.refreshed_summary),
        lane_summary_path=str(args.lane_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "mainline_task_count": (payload.get("metrics") or {}).get("mainline_task_count")}))


if __name__ == "__main__":
    main()
