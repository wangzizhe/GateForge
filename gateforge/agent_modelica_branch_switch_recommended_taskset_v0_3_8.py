from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_branch_switch_recommended_taskset_v0_3_8"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_recommended_taskset_v0_3_8"


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


def build_branch_switch_recommended_taskset(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    rows = refreshed.get("tasks")
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    selected = [row for row in rows if row.get("success_after_branch_switch") is True]
    task_ids = [str(row.get("task_id") or "") for row in selected]
    protocol = {}
    if selected and isinstance(selected[0].get("baseline_measurement_protocol"), dict):
        protocol = dict(selected[0]["baseline_measurement_protocol"])

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if len(selected) >= 3 else "EMPTY",
        "source_refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "task_count": len(selected),
        "task_ids": task_ids,
        "baseline_measurement_protocol": protocol,
        "tasks": selected,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.8 Branch-Switch Recommended Taskset",
                "",
                f"- status: `{payload['status']}`",
                f"- task_count: `{payload['task_count']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the explicit branch-switch subset from the v0.3.8 refreshed authority results.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_branch_switch_recommended_taskset(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
