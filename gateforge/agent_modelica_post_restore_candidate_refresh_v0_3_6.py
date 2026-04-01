from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_post_restore_family_spec_v0_3_6 import (
    build_lane_summary,
)


SCHEMA_VERSION = "agent_modelica_post_restore_candidate_refresh_v0_3_6"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_post_restore_candidate_refresh_v0_3_6"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _result_rows(payload: dict) -> list[dict]:
    rows = payload.get("results")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _classifier_rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _attempts(row: dict) -> list[dict]:
    attempts = row.get("attempts")
    if isinstance(attempts, list):
        return [attempt for attempt in attempts if isinstance(attempt, dict)]
    return []


def _first_llm_guided_round(attempts: list[dict]) -> int:
    for attempt in attempts:
        params = attempt.get("llm_plan_candidate_parameters")
        directions = attempt.get("llm_plan_candidate_value_directions")
        if (isinstance(params, list) and params) or (isinstance(directions, list) and directions):
            return int(attempt.get("round") or 0)
    return 0


def _infer_single_sweep_fields(result: dict) -> dict:
    direct_outcome = _norm(result.get("single_sweep_outcome"))
    direct_first_success = result.get("first_correction_success")
    direct_residual = result.get("residual_failure_after_first_correction")
    if direct_outcome or direct_first_success is not None or direct_residual is not None:
        return {
            "single_sweep_outcome": direct_outcome,
            "first_correction_success": bool(direct_first_success),
            "residual_failure_after_first_correction": bool(direct_residual),
        }

    attempts = _attempts(result)
    if not attempts:
        return {
            "single_sweep_outcome": "",
            "first_correction_success": False,
            "residual_failure_after_first_correction": False,
        }

    first_guided_round = _first_llm_guided_round(attempts)
    if first_guided_round <= 0:
        return {
            "single_sweep_outcome": "",
            "first_correction_success": False,
            "residual_failure_after_first_correction": False,
        }

    later_attempts = [
        attempt for attempt in attempts
        if int(attempt.get("round") or 0) > first_guided_round
    ]
    if not later_attempts:
        return {
            "single_sweep_outcome": "",
            "first_correction_success": False,
            "residual_failure_after_first_correction": False,
        }

    last_attempt = later_attempts[-1]
    any_intermediate_failure = any(not bool(attempt.get("simulate_pass")) for attempt in later_attempts[:-1])
    final_success = bool(last_attempt.get("simulate_pass"))
    if final_success and any_intermediate_failure:
        return {
            "single_sweep_outcome": "residual_failure_after_first_correction",
            "first_correction_success": True,
            "residual_failure_after_first_correction": True,
        }
    if final_success:
        return {
            "single_sweep_outcome": "resolved",
            "first_correction_success": True,
            "residual_failure_after_first_correction": False,
        }
    return {
        "single_sweep_outcome": "",
        "first_correction_success": False,
        "residual_failure_after_first_correction": False,
    }


def refresh_post_restore_candidates(
    *,
    candidate_taskset_path: str,
    results_path: str,
    classifier_summary_path: str = "",
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    taskset = _load_json(candidate_taskset_path)
    results_payload = _load_json(results_path)
    classifier_payload = _load_json(classifier_summary_path) if classifier_summary_path else {}

    tasks = _task_rows(taskset)
    results_index = {
        _item_id(row): row
        for row in _result_rows(results_payload)
        if _item_id(row)
    }
    result_dir = Path(results_path).resolve().parent if Path(results_path).exists() else Path(results_path).parent
    classifier_index = {
        _item_id(row): row
        for row in _classifier_rows(classifier_payload)
        if _item_id(row)
    }

    top_protocol = (
        results_payload.get("baseline_measurement_protocol")
        if isinstance(results_payload.get("baseline_measurement_protocol"), dict)
        else {}
    )

    refreshed_rows: list[dict] = []
    matched_result_count = 0
    matched_classifier_count = 0

    for row in tasks:
        item_id = _item_id(row)
        result = dict(results_index.get(item_id, {}) or {})
        sidecar_result_path = result_dir / f"{item_id}_result.json"
        sidecar_result = _load_json(sidecar_result_path)
        if sidecar_result:
            result = {**sidecar_result, **result}
        classifier = classifier_index.get(item_id, {})
        if result:
            matched_result_count += 1
        if classifier:
            matched_classifier_count += 1

        row_protocol = (
            result.get("baseline_measurement_protocol")
            if isinstance(result.get("baseline_measurement_protocol"), dict)
            else {}
        )
        protocol = row_protocol or top_protocol or row.get("baseline_measurement_protocol") or {}
        inferred = _infer_single_sweep_fields(result)

        merged = {
            **row,
            "verdict": _norm(result.get("verdict") or row.get("verdict")),
            "executor_status": _norm(result.get("executor_status") or row.get("executor_status")),
            "resolution_path": _norm(result.get("resolution_path") or row.get("resolution_path")),
            "planner_invoked": result.get("planner_invoked") if "planner_invoked" in result else row.get("planner_invoked"),
            "rounds_used": int(result.get("rounds_used") or row.get("rounds_used") or 0),
            "llm_request_count": int(
                result.get("llm_request_count")
                or result.get("llm_request_count_delta")
                or row.get("llm_request_count")
                or 0
            ),
            "single_sweep_outcome": _norm(inferred.get("single_sweep_outcome") or row.get("single_sweep_outcome")),
            "first_correction_success": bool(
                inferred.get("first_correction_success")
                if "first_correction_success" in inferred
                else row.get("first_correction_success")
            ),
            "residual_failure_after_first_correction": bool(
                inferred.get("residual_failure_after_first_correction")
                if "residual_failure_after_first_correction" in inferred
                else row.get("residual_failure_after_first_correction")
            ),
            "baseline_measurement_protocol": protocol,
            "check_model_pass": result.get("check_model_pass") if "check_model_pass" in result else row.get("check_model_pass"),
            "simulate_pass": result.get("simulate_pass") if "simulate_pass" in result else row.get("simulate_pass"),
            "wrong_branch_entered": result.get("wrong_branch_entered") if "wrong_branch_entered" in result else row.get("wrong_branch_entered"),
            "correct_branch_selected": result.get("correct_branch_selected") if "correct_branch_selected" in result else row.get("correct_branch_selected"),
            "error_message": _norm(result.get("error_message") or row.get("error_message")),
            "post_restore_failure_bucket": _norm(
                classifier.get("post_restore_failure_bucket")
                or result.get("post_restore_failure_bucket")
                or row.get("post_restore_failure_bucket")
            ),
            "post_restore_bucket_reasons": list(
                classifier.get("post_restore_bucket_reasons")
                or result.get("post_restore_bucket_reasons")
                or row.get("post_restore_bucket_reasons")
                or []
            ),
        }
        refreshed_rows.append(merged)

    lane_summary = build_lane_summary(refreshed_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "results_path": str(Path(results_path).resolve()) if Path(results_path).exists() else str(results_path),
        "classifier_summary_path": (
            str(Path(classifier_summary_path).resolve()) if classifier_summary_path and Path(classifier_summary_path).exists() else str(classifier_summary_path)
        ),
        "metrics": {
            "task_count": len(tasks),
            "matched_result_count": matched_result_count,
            "matched_classifier_count": matched_classifier_count,
        },
        "tasks": refreshed_rows,
        "lane_summary": lane_summary,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "taskset_candidates_refreshed.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lane_summary = payload.get("lane_summary") if isinstance(payload.get("lane_summary"), dict) else {}
    lines = [
        "# Post-Restore Candidate Refresh v0.3.6",
        "",
        f"- status: `{payload.get('status')}`",
        f"- matched_result_count: `{metrics.get('matched_result_count')}`",
        f"- matched_classifier_count: `{metrics.get('matched_classifier_count')}`",
        f"- lane_status: `{lane_summary.get('lane_status')}`",
        f"- admitted_count: `{lane_summary.get('admitted_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh v0.3.6 post-restore candidates with live results and failure buckets.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--classifier-summary", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = refresh_post_restore_candidates(
        candidate_taskset_path=str(args.candidate_taskset),
        results_path=str(args.results),
        classifier_summary_path=str(args.classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "lane_status": (payload.get("lane_summary") or {}).get("lane_status")}))


if __name__ == "__main__":
    main()
