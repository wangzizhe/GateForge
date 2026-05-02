from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_blind_gate_v0_36_4 import lint_benchmark_blindness
from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VARIANTS = REPO_ROOT / "artifacts" / "hard_core_adjacent_variants_v0_48_1" / "tasks.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_adjacent_gate_v0_48_2"


REQUIRED_LINEAGE_FIELDS = ("anchor_case_id", "variant_axis", "generation")


def _lineage_status(task: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []
    lineage = task.get("lineage") if isinstance(task.get("lineage"), dict) else {}
    for field in REQUIRED_LINEAGE_FIELDS:
        if not str(lineage.get(field) or "").strip():
            issues.append(f"missing_lineage_{field}")
    return ("PASS" if not issues else "REVIEW"), issues


def gate_adjacent_variant(task: dict[str, Any]) -> dict[str, Any]:
    blind = lint_benchmark_blindness(
        {
            "case_id": task.get("case_id"),
            "description": task.get("description"),
            "constraints": task.get("constraints") or [],
        }
    )
    lineage_status, lineage_issues = _lineage_status(task)
    has_model = bool(str(task.get("initial_model") or "").strip())
    has_verification = bool((task.get("verification") or {}).get("check_model"))
    issues = []
    if blind["status"] != "PASS":
        issues.append("blind_lint_failed")
    issues.extend(lineage_issues)
    if not has_model:
        issues.append("missing_initial_model")
    if not has_verification:
        issues.append("missing_check_model_verification")
    return {
        "case_id": str(task.get("case_id") or ""),
        "anchor_case_id": str((task.get("lineage") or {}).get("anchor_case_id") or ""),
        "blind_lint_status": blind["status"],
        "blind_lint_hit_count": int(blind.get("leakage_risk_count") or 0),
        "lineage_status": lineage_status,
        "offline_gate_status": "PASS" if not issues else "REVIEW",
        "issues": issues,
    }


def build_hard_core_adjacent_gate(
    *,
    variants: list[dict[str, Any]],
    version: str = "v0.48.2",
) -> dict[str, Any]:
    rows = [gate_adjacent_variant(task) for task in variants]
    pass_rows = [row for row in rows if row["offline_gate_status"] == "PASS"]
    anchor_counts: dict[str, int] = {}
    for row in pass_rows:
        anchor = str(row["anchor_case_id"])
        anchor_counts[anchor] = anchor_counts.get(anchor, 0) + 1
    return {
        "version": version,
        "analysis_scope": "hard_core_adjacent_offline_gate",
        "status": "PASS" if variants and len(pass_rows) == len(variants) else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "variant_count": len(variants),
        "offline_gate_pass_count": len(pass_rows),
        "offline_gate_review_count": len(rows) - len(pass_rows),
        "passed_case_ids": [row["case_id"] for row in pass_rows],
        "passed_anchor_counts": dict(sorted(anchor_counts.items())),
        "results": sorted(rows, key=lambda item: item["case_id"]),
        "next_action": "run_omc_admission_then_base_tool_use_baseline",
        "scope_note": (
            "Offline gate checks blind prompt, lineage, and task shape only. It does not establish OMC admission, "
            "hardness, or Agent capability."
        ),
    }


def write_hard_core_adjacent_gate_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "passed_case_ids.txt").write_text(
        "\n".join(summary.get("passed_case_ids") or []) + "\n",
        encoding="utf-8",
    )


def run_hard_core_adjacent_gate(
    *,
    variants_path: Path = DEFAULT_VARIANTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_hard_core_adjacent_gate(variants=load_jsonl(variants_path))
    write_hard_core_adjacent_gate_outputs(out_dir=out_dir, summary=summary)
    return summary
