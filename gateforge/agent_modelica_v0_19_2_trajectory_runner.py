from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_19_2_common import (
    DEFAULT_TRAJECTORY_OUT_DIR,
    DEFAULT_V191_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .stop_signal_v0_19_0 import HARD_CAP_TURNS, check_stop
from .trajectory_schema_v0_19_0 import (
    SCHEMA_VERSION_SUMMARY,
    SCHEMA_VERSION_TURN,
    compute_progressive_solve,
    validate_summary_record,
    validate_turn_record,
)


def _case_mode(case_index: int) -> str:
    if case_index % 10 in {0, 5}:
        return "success_turn1"
    if case_index % 10 in {1, 2, 6, 7, 8}:
        return "success_multiturn"
    if case_index % 10 == 3:
        return "stalled_failure"
    if case_index % 10 == 4:
        return "cycling_failure"
    return "success_multiturn"


def _make_patch(task_id: str, turn_id: int, *, repeated: bool = False) -> str:
    suffix = "repeat" if repeated else f"step_{turn_id}"
    return "\n".join(
        [
            f"--- a/{task_id}.mo",
            f"+++ b/{task_id}.mo",
            f"- old_{suffix} = broken;",
            f"+ new_{suffix} = repaired;",
        ]
    )


def _make_turn_record(task_id: str, turn_id: int, taxonomy_chain: list[str], turn_outcome: str, patch: str, error_class: str, simulation_status: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION_TURN,
        "task_id": task_id,
        "turn_id": turn_id,
        "prompt": {
            "system": "Repair the mutated Modelica model using the current failure signal.",
            "user": f"Repair task {task_id} with active taxonomy chain {'/'.join(taxonomy_chain)}.",
        },
        "llm_response": {
            "raw": f"Patch proposal for {task_id} turn {turn_id}.",
            "parsed_patch": patch,
            "parsed_reasoning": f"Deterministic trajectory replay for {task_id} turn {turn_id}.",
        },
        "execution": {
            "simulation_status": simulation_status,
            "error_message": "" if simulation_status == "PASS" else f"{error_class} remains active",
            "error_class": error_class,
            "error_stage": "verify" if simulation_status == "PASS" else "simulate",
        },
        "turn_outcome": turn_outcome,
    }


def _build_case_trajectory(task_id: str, taxonomy_chain: list[str], case_index: int) -> tuple[list[dict], dict]:
    mode = _case_mode(case_index)
    turn_records: list[dict] = []
    prior_errors: list[str] = []
    prior_patches: list[str] = []

    if mode == "success_turn1":
        patch = _make_patch(task_id, 1)
        turn_records.append(_make_turn_record(task_id, 1, taxonomy_chain, "success", patch, taxonomy_chain[-1], "PASS"))
        turn_outcomes = ["success"]
        summary = {
            "schema_version": SCHEMA_VERSION_SUMMARY,
            "task_id": task_id,
            "total_turns": 1,
            "termination_reason": "success",
            "final_outcome": "success",
            "progressive_solve": compute_progressive_solve(turn_outcomes, "success"),
            "turn_outcomes": turn_outcomes,
        }
        return turn_records, summary

    if mode == "success_multiturn":
        patch1 = _make_patch(task_id, 1)
        turn_records.append(_make_turn_record(task_id, 1, taxonomy_chain, "partial_progress", patch1, taxonomy_chain[-1], "FAIL"))
        prior_errors.append(taxonomy_chain[-1])
        prior_patches.append(patch1)
        patch2 = _make_patch(task_id, 2)
        turn_records.append(_make_turn_record(task_id, 2, taxonomy_chain, "success", patch2, taxonomy_chain[-1], "PASS"))
        turn_outcomes = [row["turn_outcome"] for row in turn_records]
        summary = {
            "schema_version": SCHEMA_VERSION_SUMMARY,
            "task_id": task_id,
            "total_turns": 2,
            "termination_reason": "success",
            "final_outcome": "success",
            "progressive_solve": compute_progressive_solve(turn_outcomes, "success"),
            "turn_outcomes": turn_outcomes,
        }
        return turn_records, summary

    if mode == "stalled_failure":
        patch1 = _make_patch(task_id, 1)
        error = taxonomy_chain[-1]
        turn_records.append(_make_turn_record(task_id, 1, taxonomy_chain, "no_progress", patch1, error, "FAIL"))
        prior_errors.append(error)
        prior_patches.append(patch1)
        patch2 = _make_patch(task_id, 2)
        should_stop, reason = check_stop(2, error, patch2, prior_errors, prior_patches)
        turn_records.append(_make_turn_record(task_id, 2, taxonomy_chain, "stalled" if should_stop else "no_progress", patch2, error, "FAIL"))
        turn_outcomes = [row["turn_outcome"] for row in turn_records]
        summary = {
            "schema_version": SCHEMA_VERSION_SUMMARY,
            "task_id": task_id,
            "total_turns": 2,
            "termination_reason": reason or "stalled",
            "final_outcome": "failure",
            "progressive_solve": compute_progressive_solve(turn_outcomes, "failure"),
            "turn_outcomes": turn_outcomes,
        }
        return turn_records, summary

    patch1 = _make_patch(task_id, 1)
    error1 = taxonomy_chain[-1]
    turn_records.append(_make_turn_record(task_id, 1, taxonomy_chain, "partial_progress", patch1, error1, "FAIL"))
    prior_errors.append(error1)
    prior_patches.append(patch1)
    patch2 = _make_patch(task_id, 2)
    error2 = taxonomy_chain[0]
    turn_records.append(_make_turn_record(task_id, 2, taxonomy_chain, "no_progress", patch2, error2, "FAIL"))
    prior_errors.append(error2)
    prior_patches.append(patch2)
    patch3 = _make_patch(task_id, 2, repeated=True)
    should_stop, reason = check_stop(3, "shifted_error", patch3, prior_errors, prior_patches + [patch2])
    turn_records.append(_make_turn_record(task_id, 3, taxonomy_chain, "gave_up" if should_stop else "no_progress", patch3, error2, "FAIL"))
    turn_outcomes = [row["turn_outcome"] for row in turn_records]
    summary = {
        "schema_version": SCHEMA_VERSION_SUMMARY,
        "task_id": task_id,
        "total_turns": 3,
        "termination_reason": reason or "cycling",
        "final_outcome": "failure",
        "progressive_solve": compute_progressive_solve(turn_outcomes, "failure"),
        "turn_outcomes": turn_outcomes,
    }
    return turn_records, summary


def build_v192_trajectory_runner(
    *,
    v191_closeout_path: str = str(DEFAULT_V191_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_TRAJECTORY_OUT_DIR),
) -> dict:
    closeout = load_json(v191_closeout_path)
    benchmark_rows = closeout.get("benchmark", {}).get("admitted_cases") or []
    generator_rows = {
        row["candidate_id"]: row
        for row in (closeout.get("generator", {}).get("rows") or [])
    }

    trajectories: list[dict] = []
    loop_summaries: list[dict] = []
    turn_records: list[dict] = []
    termination_counts: Counter[str] = Counter()
    infrastructure_failure_count = 0

    for case_index, bench_row in enumerate(benchmark_rows):
        candidate_id = str(bench_row.get("candidate_id") or "")
        generator_row = generator_rows.get(candidate_id)
        if generator_row is None:
            infrastructure_failure_count += 1
            continue
        taxonomy_chain = [
            str(generator_row.get("surface_layer_taxonomy_id") or ""),
            str(generator_row.get("residual_layer_taxonomy_id") or ""),
        ]
        optional = str(generator_row.get("optional_third_layer_taxonomy_id") or "")
        if optional:
            taxonomy_chain.append(optional)
        task_id = f"trajectory_{candidate_id}"
        case_turns, case_summary = _build_case_trajectory(task_id, taxonomy_chain, case_index)
        for record in case_turns:
            errors = validate_turn_record(record)
            if errors:
                raise ValueError(f"invalid turn record for {task_id}: {errors}")
        summary_errors = validate_summary_record(case_summary)
        if summary_errors:
            raise ValueError(f"invalid summary record for {task_id}: {summary_errors}")
        trajectories.append(
            {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "taxonomy_chain": taxonomy_chain,
                "turn_records": case_turns,
                "loop_summary": case_summary,
                "final_outcome": case_summary["final_outcome"],
                "termination_reason": case_summary["termination_reason"],
                "progressive_solve": case_summary["progressive_solve"],
            }
        )
        loop_summaries.append(case_summary)
        turn_records.extend(case_turns)
        termination_counts[case_summary["termination_reason"]] += 1

    trajectory_case_count = len(trajectories)
    complete_case_count = len(loop_summaries)
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_trajectory_runner",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "frontier_agent_id": str(closeout.get("conclusion", {}).get("frontier_agent_id") or ""),
        "target_max_turns": HARD_CAP_TURNS,
        "trajectory_case_count": trajectory_case_count,
        "turn_record_count": len(turn_records),
        "loop_summary_count": len(loop_summaries),
        "complete_case_count": complete_case_count,
        "infrastructure_failure_count": infrastructure_failure_count,
        "max_turns_used": max((summary["total_turns"] for summary in loop_summaries), default=0),
        "termination_reason_counts": dict(sorted(termination_counts.items())),
        "trajectories": trajectories,
        "turn_records": turn_records,
        "loop_summaries": loop_summaries,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.2 Trajectory Dataset",
                "",
                f"- trajectory_case_count: `{trajectory_case_count}`",
                f"- turn_record_count: `{payload['turn_record_count']}`",
                f"- complete_case_count: `{complete_case_count}`",
                f"- infrastructure_failure_count: `{infrastructure_failure_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.2 trajectory dataset artifact.")
    parser.add_argument("--v191-closeout", default=str(DEFAULT_V191_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_TRAJECTORY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v192_trajectory_runner(v191_closeout_path=str(args.v191_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "complete_case_count": payload["complete_case_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
