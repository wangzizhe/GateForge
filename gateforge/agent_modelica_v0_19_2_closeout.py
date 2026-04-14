from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from .agent_modelica_v0_19_2_capability_profile import build_v192_capability_profile
from .agent_modelica_v0_19_2_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_METRIC_OUT_DIR,
    DEFAULT_PROFILE_OUT_DIR,
    DEFAULT_TRAJECTORY_OUT_DIR,
    DEFAULT_V190_CLOSEOUT_PATH,
    DEFAULT_V191_CLOSEOUT_PATH,
    READY_MAX_INFRA_FAILURES,
    READY_MIN_COMPLETE_CASES,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_19_2_handoff_integrity import build_v192_handoff_integrity
from .agent_modelica_v0_19_2_metric_report import build_v192_metric_report
from .agent_modelica_v0_19_2_trajectory_runner import build_v192_trajectory_runner


def build_v192_closeout(
    *,
    v190_closeout_path: str = str(DEFAULT_V190_CLOSEOUT_PATH),
    v191_closeout_path: str = str(DEFAULT_V191_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    trajectory_summary_path: str = str(DEFAULT_TRAJECTORY_OUT_DIR / "summary.json"),
    metric_summary_path: str = str(DEFAULT_METRIC_OUT_DIR / "summary.json"),
    profile_summary_path: str = str(DEFAULT_PROFILE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
    executor_cmd: list[str] | None = None,
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v192_handoff_integrity(
            v190_closeout_path=v190_closeout_path,
            v191_closeout_path=v191_closeout_path,
            out_dir=str(Path(handoff_integrity_path).parent),
        )
    if not Path(trajectory_summary_path).exists():
        build_v192_trajectory_runner(
            v191_closeout_path=v191_closeout_path,
            out_dir=str(Path(trajectory_summary_path).parent),
            executor_cmd=executor_cmd,
        )
    if not Path(metric_summary_path).exists():
        build_v192_metric_report(trajectory_summary_path=trajectory_summary_path, out_dir=str(Path(metric_summary_path).parent))
    if not Path(profile_summary_path).exists():
        build_v192_capability_profile(trajectory_summary_path=trajectory_summary_path, out_dir=str(Path(profile_summary_path).parent))

    handoff = load_json(handoff_integrity_path)
    trajectory = load_json(trajectory_summary_path)
    metrics = load_json(metric_summary_path)
    profile = load_json(profile_summary_path)

    handoff_ok = handoff.get("handoff_integrity_status") == "PASS"
    trajectory_case_count = int(trajectory.get("trajectory_case_count") or 0)
    complete_case_count = int(trajectory.get("complete_case_count") or 0)
    loop_summary_count = int(trajectory.get("loop_summary_count") or 0)
    infrastructure_failure_count = int(trajectory.get("infrastructure_failure_count") or 0)
    metrics_ok = str(metrics.get("metric_report_status") or "") == "PASS"
    profile_ok = str(profile.get("capability_profile_status") or "") == "PASS"

    ready = (
        handoff_ok
        and complete_case_count >= READY_MIN_COMPLETE_CASES
        and trajectory_case_count >= READY_MIN_COMPLETE_CASES
        and loop_summary_count == complete_case_count
        and infrastructure_failure_count <= READY_MAX_INFRA_FAILURES
        and metrics_ok
        and profile_ok
    )

    if not handoff_ok:
        version_decision = "v0_19_2_foundation_inputs_invalid"
        status = "FAIL"
        handoff_mode = "rebuild_v0_19_2_from_valid_benchmark_inputs"
    elif ready:
        version_decision = "v0_19_2_first_real_multiturn_trajectory_dataset_ready"
        status = "PASS"
        handoff_mode = "characterize_and_expand_trajectory_learning_value"
    else:
        version_decision = "v0_19_2_trajectory_dataset_partial"
        status = "PASS"
        handoff_mode = "repair_trajectory_collection_gaps_without_reopening_foundation_or_benchmark"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_closeout",
        "generated_at_utc": now_utc(),
        "status": status,
        "closeout_status": version_decision.upper(),
        "conclusion": {
            "version_decision": version_decision,
            "trajectory_case_count": trajectory_case_count,
            "turn_record_count": int(trajectory.get("turn_record_count") or 0),
            "complete_case_count": complete_case_count,
            "loop_summary_count": loop_summary_count,
            "infrastructure_failure_count": infrastructure_failure_count,
            "turn_1_success_rate": metrics.get("turn_1_success_rate"),
            "turn_n_success_rate": metrics.get("turn_n_success_rate"),
            "progressive_solve_rate": metrics.get("progressive_solve_rate"),
            "v0_19_3_handoff_mode": handoff_mode,
        },
        "handoff_integrity": handoff,
        "trajectory_dataset": trajectory,
        "metric_report": metrics,
        "capability_profile": profile,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.2 Closeout",
                "",
                f"- version_decision: `{version_decision}`",
                f"- complete_case_count: `{complete_case_count}`",
                f"- trajectory_case_count: `{trajectory_case_count}`",
                f"- progressive_solve_rate: `{metrics.get('progressive_solve_rate')}`",
                f"- v0_19_3_handoff_mode: `{handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.2 trajectory dataset closeout.")
    parser.add_argument("--v190-closeout", default=str(DEFAULT_V190_CLOSEOUT_PATH))
    parser.add_argument("--v191-closeout", default=str(DEFAULT_V191_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--trajectory-summary", default=str(DEFAULT_TRAJECTORY_OUT_DIR / "summary.json"))
    parser.add_argument("--metric-summary", default=str(DEFAULT_METRIC_OUT_DIR / "summary.json"))
    parser.add_argument("--profile-summary", default=str(DEFAULT_PROFILE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    parser.add_argument("--executor-cmd", default="")
    args = parser.parse_args()
    executor_cmd = shlex.split(str(args.executor_cmd)) if str(args.executor_cmd or "").strip() else None
    payload = build_v192_closeout(
        v190_closeout_path=str(args.v190_closeout),
        v191_closeout_path=str(args.v191_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        trajectory_summary_path=str(args.trajectory_summary),
        metric_summary_path=str(args.metric_summary),
        profile_summary_path=str(args.profile_summary),
        out_dir=str(args.out_dir),
        executor_cmd=executor_cmd,
    )
    print(json.dumps({"status": payload["status"], "version_decision": payload["conclusion"]["version_decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
