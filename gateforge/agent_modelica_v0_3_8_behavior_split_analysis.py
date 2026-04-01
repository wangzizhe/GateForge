from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_8_behavior_split_analysis"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_8_behavior_split_analysis"


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


def build_v0_3_8_behavior_split_analysis(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    rows = refreshed.get("tasks")
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    explicit = [str(row.get("task_id") or "") for row in rows if row.get("success_after_branch_switch") is True]
    absorbed = [str(row.get("task_id") or "") for row in rows if bool(row.get("success_without_branch_switch_evidence"))]
    mixed_branch_sequences = [
        str(row.get("task_id") or "")
        for row in rows
        if isinstance(row.get("detected_branch_sequence"), list) and len(row.get("detected_branch_sequence") or []) >= 2 and row.get("success_after_branch_switch") is not True
    ]
    metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}

    explicit_count = len(explicit)
    absorbed_count = len(absorbed)
    if explicit_count > absorbed_count:
        mainline_success_mode = "branch_switch_evidenced_dominant"
    elif explicit_count == absorbed_count and explicit_count > 0:
        mainline_success_mode = "split_co_dominant"
    elif absorbed_count > 0:
        mainline_success_mode = "absorbed_success_still_dominant"
    else:
        mainline_success_mode = "no_success_signal"

    if explicit_count >= 3 and absorbed_count == 0:
        status = "PROMOTION_READY"
        recommendation = "branch_switch_replan_after_stall"
    elif explicit_count >= 3:
        status = "PARTIAL_FORCING"
        recommendation = "explicit_branch_switch_subfamily_selection"
    else:
        status = "INSUFFICIENT_SIGNAL"
        recommendation = "stronger_behavior_forcing_lane_design"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "source_refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "metrics": {
            "total_rows": int(metrics.get("total_rows") or 0),
            "successful_case_count": int(metrics.get("successful_case_count") or 0),
            "success_after_branch_switch_count": explicit_count,
            "success_without_branch_switch_evidence_count": absorbed_count,
            "branch_switch_evidenced_success_pct": float(metrics.get("branch_switch_evidenced_success_pct") or 0.0),
            "success_without_branch_switch_evidence_pct": float(metrics.get("success_without_branch_switch_evidence_pct") or 0.0),
            "mixed_branch_sequence_without_success_count": len(mixed_branch_sequences),
        },
        "mainline_success_mode": mainline_success_mode,
        "recommendation": recommendation,
        "explicit_branch_switch_task_ids": explicit,
        "absorbed_success_task_ids": absorbed,
        "mixed_branch_sequence_without_success_task_ids": mixed_branch_sequences,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.8 Behavior Split Analysis",
                "",
                f"- status: `{status}`",
                f"- mainline_success_mode: `{mainline_success_mode}`",
                f"- recommendation: `{recommendation}`",
                f"- explicit_branch_switch_task_count: `{explicit_count}`",
                f"- absorbed_success_task_count: `{absorbed_count}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize the explicit-branch-switch vs absorbed-success split for v0.3.8.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_8_behavior_split_analysis(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "recommendation": payload.get("recommendation")}))


if __name__ == "__main__":
    main()
