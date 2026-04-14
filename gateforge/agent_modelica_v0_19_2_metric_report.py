from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_19_2_common import (
    DEFAULT_METRIC_OUT_DIR,
    DEFAULT_TRAJECTORY_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v192_metric_report(
    *,
    trajectory_summary_path: str = str(DEFAULT_TRAJECTORY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_METRIC_OUT_DIR),
) -> dict:
    dataset = load_json(trajectory_summary_path)
    trajectories = dataset.get("trajectories") or []
    loop_summaries = dataset.get("loop_summaries") or []

    complete_case_count = int(dataset.get("complete_case_count") or 0)
    turn1_success_count = 0
    turnn_success_count = 0
    success_turns: list[int] = []
    progressive_solve_count = 0
    eligible_recovery_denominator = 0
    recovery_numerator = 0

    for trajectory in trajectories:
        turns = trajectory.get("turn_records") or []
        if turns and turns[0].get("turn_outcome") == "success":
            turn1_success_count += 1
        if trajectory.get("final_outcome") == "success":
            turnn_success_count += 1
            success_turns.append(int(trajectory.get("loop_summary", {}).get("total_turns") or 0))
        if bool(trajectory.get("progressive_solve")):
            progressive_solve_count += 1
        for idx, turn in enumerate(turns[:-1]):
            current_outcome = str(turn.get("turn_outcome") or "")
            if current_outcome in {"no_progress", "partial_progress"}:
                eligible_recovery_denominator += 1
                next_outcome = str(turns[idx + 1].get("turn_outcome") or "")
                if next_outcome in {"partial_progress", "success"}:
                    recovery_numerator += 1

    recovery_defined = eligible_recovery_denominator > 0
    recovery_rate = round(recovery_numerator / eligible_recovery_denominator, 4) if recovery_defined else None
    termination_reason_distribution = {}
    for key, count in (dataset.get("termination_reason_counts") or {}).items():
        termination_reason_distribution[key] = {
            "count": int(count),
            "rate": round(int(count) / complete_case_count, 4) if complete_case_count else 0.0,
        }

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_metric_report",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "metric_report_status": "PASS",
        "complete_case_count": complete_case_count,
        "turn_1_success_rate": round(turn1_success_count / complete_case_count, 4) if complete_case_count else 0.0,
        "turn_n_success_rate": round(turnn_success_count / complete_case_count, 4) if complete_case_count else 0.0,
        "average_turns_to_success": round(sum(success_turns) / len(success_turns), 4) if success_turns else None,
        "recovery_rate": recovery_rate,
        "recovery_rate_defined": recovery_defined,
        "progressive_solve_rate": round(progressive_solve_count / complete_case_count, 4) if complete_case_count else 0.0,
        "termination_reason_distribution": termination_reason_distribution,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.2 Trajectory Metrics",
                "",
                f"- turn_1_success_rate: `{payload['turn_1_success_rate']}`",
                f"- turn_n_success_rate: `{payload['turn_n_success_rate']}`",
                f"- recovery_rate: `{payload['recovery_rate']}`",
                f"- progressive_solve_rate: `{payload['progressive_solve_rate']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.2 trajectory metric report artifact.")
    parser.add_argument("--trajectory-summary", default=str(DEFAULT_TRAJECTORY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_METRIC_OUT_DIR))
    args = parser.parse_args()
    payload = build_v192_metric_report(trajectory_summary_path=str(args.trajectory_summary), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "metric_report_status": payload["metric_report_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
