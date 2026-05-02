from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VARIANTS = REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1" / "tasks.jsonl"
DEFAULT_ADMITTED = REPO_ROOT / "artifacts" / "hard_core_adjacent_admission_v0_48_3" / "admitted_case_ids.txt"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_plan_v0_48_4"


def _load_case_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def build_hard_core_adjacent_baseline_plan(
    *,
    variants: list[dict[str, Any]],
    admitted_case_ids: set[str],
    version: str = "v0.48.4",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for task in variants:
        case_id = str(task.get("case_id") or "")
        if case_id not in admitted_case_ids:
            continue
        rows.append(
            {
                "case_id": case_id,
                "runner_mode": "tool_use",
                "tool_profile": "base",
                "max_steps": 10,
                "max_token_budget": 32000,
                "provider_model_source": "environment",
                "wrapper_repair": "forbidden",
                "expected_evidence_role": "formal_experiment",
                "repeatability_required_for_hard_negative": True,
            }
        )
    anchor_counts: dict[str, int] = {}
    by_case = {str(task.get("case_id") or ""): task for task in variants}
    for row in rows:
        lineage = by_case[row["case_id"]].get("lineage") or {}
        anchor = str(lineage.get("anchor_case_id") or "")
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
    summary = {
        "version": version,
        "analysis_scope": "hard_core_adjacent_baseline_plan",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "planned_run_count": len(rows),
        "anchor_counts": dict(sorted(anchor_counts.items())),
        "case_ids": [row["case_id"] for row in rows],
        "runner_contract": {
            "provider_model_source": "environment",
            "tool_profile": "base",
            "wrapper_repair": "forbidden",
            "hidden_routing": "forbidden",
            "deterministic_patch": "forbidden",
        },
        "next_action": "run_base_tool_use_baseline_then_repeat_failures",
    }
    return summary, rows


def write_hard_core_adjacent_baseline_plan_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "run_plan.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "case_ids.txt").write_text("\n".join(row["case_id"] for row in rows) + "\n", encoding="utf-8")


def run_hard_core_adjacent_baseline_plan(
    *,
    variants_path: Path = DEFAULT_VARIANTS,
    admitted_path: Path = DEFAULT_ADMITTED,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, rows = build_hard_core_adjacent_baseline_plan(
        variants=load_jsonl(variants_path),
        admitted_case_ids=_load_case_ids(admitted_path),
    )
    write_hard_core_adjacent_baseline_plan_outputs(out_dir=out_dir, summary=summary, rows=rows)
    return summary
