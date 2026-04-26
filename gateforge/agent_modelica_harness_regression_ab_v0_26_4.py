from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "harness_regression_ab_v0_26_4"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def compute_legacy_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    pass_count = sum(1 for row in rows if row.get("final_verdict") == "PASS")
    legacy_multiturn_count = sum(
        1
        for row in rows
        if row.get("final_verdict") == "PASS" and int(row.get("executor_attempt_count") or 0) >= 2
    )
    return {
        "metric_definition": "legacy_executor_attempt_based",
        "total": total,
        "pass_count": pass_count,
        "pass_rate": _rate(pass_count, total),
        "multiturn_count": legacy_multiturn_count,
        "multiturn_rate": _rate(legacy_multiturn_count, total),
    }


def compute_current_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    pass_count = sum(1 for row in rows if row.get("final_verdict") == "PASS")
    true_multiturn_count = sum(
        1
        for row in rows
        if row.get("final_verdict") == "PASS" and int(row.get("repair_round_count") or 0) >= 2
    )
    return {
        "metric_definition": "current_repair_round_based",
        "total": total,
        "pass_count": pass_count,
        "pass_rate": _rate(pass_count, total),
        "true_multiturn_count": true_multiturn_count,
        "true_multiturn_rate": _rate(true_multiturn_count, total),
    }


def compare_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    legacy = compute_legacy_metrics(rows)
    current = compute_current_metrics(rows)
    fake_multiturn_rows = [
        {
            "run_id": row.get("run_id"),
            "case_id": row.get("case_id"),
            "executor_attempt_count": row.get("executor_attempt_count"),
            "repair_round_count": row.get("repair_round_count"),
            "final_verdict": row.get("final_verdict"),
        }
        for row in rows
        if row.get("final_verdict") == "PASS"
        and int(row.get("executor_attempt_count") or 0) >= 2
        and int(row.get("repair_round_count") or 0) < 2
    ]
    return {
        "legacy": legacy,
        "current": current,
        "pass_count_delta": int(current["pass_count"]) - int(legacy["pass_count"]),
        "pass_rate_delta": round(float(current["pass_rate"]) - float(legacy["pass_rate"]), 4),
        "multiturn_count_delta": int(current["true_multiturn_count"]) - int(legacy["multiturn_count"]),
        "multiturn_rate_delta": round(float(current["true_multiturn_rate"]) - float(legacy["multiturn_rate"]), 4),
        "fake_multiturn_row_count": len(fake_multiturn_rows),
        "fake_multiturn_rows": fake_multiturn_rows,
    }


def build_harness_regression_ab(
    *,
    input_path: Path = DEFAULT_INPUT,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    rows = load_jsonl(input_path)
    comparison = compare_metrics(rows)
    missing_input = not rows
    pass_metric_changed = comparison["pass_count_delta"] != 0 or comparison["pass_rate_delta"] != 0.0
    ready = not missing_input and not pass_metric_changed
    summary = {
        "version": "v0.26.4",
        "status": "PASS" if ready else "REVIEW",
        "analysis_scope": "harness_regression_ab",
        "input_path": str(input_path.relative_to(REPO_ROOT)) if input_path.is_relative_to(REPO_ROOT) else str(input_path),
        "trajectory_count": len(rows),
        "comparison": comparison,
        "capability_metric_changed": pass_metric_changed,
        "metric_definition_change_detected": comparison["fake_multiturn_row_count"] > 0,
        "interpretation": {
            "pass_rate_change_is_capability_change": False,
            "multiturn_delta_is_metric_definition_change": comparison["fake_multiturn_row_count"] > 0,
            "same_raw_trajectories_recomputed": True,
        },
        "discipline": {
            "llm_calls_added": False,
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "llm_capability_gain_claimed": False,
            "replay_not_live_agent_metric": True,
        },
        "decision": (
            "harness_regression_ab_passed_no_capability_metric_shift"
            if ready
            else "harness_regression_ab_needs_review"
        ),
        "next_focus": "v0.26.5_product_workflow_smoke",
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "comparison.json").write_text(
        json.dumps(summary["comparison"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
