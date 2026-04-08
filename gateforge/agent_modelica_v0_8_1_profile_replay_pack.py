from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_8_0_pilot_workflow_profile import build_v080_pilot_workflow_profile
from .agent_modelica_v0_8_1_common import (
    DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V080_SUBSTRATE_PATH,
    SCHEMA_PREFIX,
    now_utc,
    outcome_sort_key,
    range_pct,
    write_json,
    write_text,
)


def _mode_outcome(outcomes: list[str]) -> str:
    counts = Counter(outcomes)
    return sorted(counts.items(), key=lambda item: (-item[1], outcome_sort_key(item[0]), item[0]))[0][0]


def build_v081_profile_replay_pack(
    *,
    substrate_path: str = str(DEFAULT_V080_SUBSTRATE_PATH),
    out_dir: str = str(DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR),
    profile_run_count: int = 3,
) -> dict:
    out_root = Path(out_dir)
    run_rows: list[dict] = []
    metrics = defaultdict(list)
    case_outcomes: dict[str, list[str]] = defaultdict(list)

    mock_detected = False
    for run_index in range(1, profile_run_count + 1):
        run_dir = out_root / f"run_{run_index:02d}"
        profile = build_v080_pilot_workflow_profile(
            substrate_path=substrate_path,
            out_dir=str(run_dir),
        )
        if not (run_dir / "run_contract" / "summary.json").exists():
            mock_detected = True
        case_table = list(profile.get("case_result_table") or [])
        for case in case_table:
            case_outcomes[str(case.get("task_id") or "")].append(str(case.get("pilot_outcome") or ""))
        for metric_name in (
            "workflow_resolution_rate_pct",
            "goal_alignment_rate_pct",
            "surface_fix_only_rate_pct",
            "unresolved_rate_pct",
        ):
            metrics[metric_name].append(float(profile.get(metric_name) or 0.0))
        run_rows.append(
            {
                "run_index": run_index,
                "status": profile.get("status"),
                "execution_source": profile.get("execution_source"),
                "workflow_resolution_rate_pct": profile.get("workflow_resolution_rate_pct"),
                "goal_alignment_rate_pct": profile.get("goal_alignment_rate_pct"),
                "surface_fix_only_rate_pct": profile.get("surface_fix_only_rate_pct"),
                "unresolved_rate_pct": profile.get("unresolved_rate_pct"),
                "case_result_table": case_table,
            }
        )

    case_consistency_rows = []
    total_case_slots = 0
    total_consistent_slots = 0
    flip_count = 0
    for task_id in sorted(case_outcomes):
        outcomes = case_outcomes[task_id]
        canonical = _mode_outcome(outcomes)
        consistent_slots = sum(1 for value in outcomes if value == canonical)
        total_case_slots += len(outcomes)
        total_consistent_slots += consistent_slots
        if len(set(outcomes)) > 1:
            flip_count += 1
        case_consistency_rows.append(
            {
                "task_id": task_id,
                "canonical_outcome": canonical,
                "outcomes_by_run": outcomes,
                "outcome_consistency_rate_pct": round(consistent_slots / len(outcomes) * 100, 1),
                "flipped_across_runs": len(set(outcomes)) > 1,
            }
        )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_profile_replay_pack",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "profile_run_count": profile_run_count,
        "execution_source": "gateforge_run_contract_live_path",
        "mock_executor_path_used": mock_detected,
        "workflow_resolution_rate_range_pct": range_pct(metrics["workflow_resolution_rate_pct"]),
        "goal_alignment_rate_range_pct": range_pct(metrics["goal_alignment_rate_pct"]),
        "surface_fix_only_rate_range_pct": range_pct(metrics["surface_fix_only_rate_pct"]),
        "unresolved_rate_range_pct": range_pct(metrics["unresolved_rate_pct"]),
        "case_outcome_flip_count": flip_count,
        "per_case_outcome_consistency_rate_pct": round(
            total_consistent_slots / total_case_slots * 100, 1
        )
        if total_case_slots
        else 0.0,
        "runs": run_rows,
        "case_consistency_table": case_consistency_rows,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.1 Profile Replay Pack",
                "",
                f"- profile_run_count: `{profile_run_count}`",
                f"- execution_source: `{payload['execution_source']}`",
                f"- workflow_resolution_rate_range_pct: `{payload['workflow_resolution_rate_range_pct']}`",
                f"- per_case_outcome_consistency_rate_pct: `{payload['per_case_outcome_consistency_rate_pct']}`",
                f"- case_outcome_flip_count: `{flip_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.1 profile replay pack.")
    parser.add_argument("--substrate-path", default=str(DEFAULT_V080_SUBSTRATE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR))
    parser.add_argument("--profile-run-count", type=int, default=3)
    args = parser.parse_args()
    payload = build_v081_profile_replay_pack(
        substrate_path=str(args.substrate_path),
        out_dir=str(args.out_dir),
        profile_run_count=int(args.profile_run_count),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
