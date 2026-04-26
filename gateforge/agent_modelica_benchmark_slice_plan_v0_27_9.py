from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_slice_review_v0_27_2 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROLE_REGISTRY = REPO_ROOT / "artifacts" / "benchmark_role_registry_v0_27_8" / "family_roles.jsonl"
DEFAULT_MANIFEST = REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3" / "manifest_rows.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_slice_plan_v0_27_9"


def _roles_by_family(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("family") or ""): row for row in rows if row.get("family")}


def _slice_role_for_manifest_row(row: dict[str, Any], family_role: str) -> str:
    split = str(row.get("split") or "")
    repeatability = str(row.get("repeatability_class") or "")
    if family_role == "capability_baseline_candidate" and split == "positive" and repeatability == "stable_true_multi":
        return "capability_baseline"
    if family_role == "hard_negative":
        return "hard_negative"
    if family_role == "diagnostic":
        return "diagnostic"
    return "excluded"


def build_benchmark_slice_plan(
    *,
    role_rows: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
    max_per_slice: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    roles = _roles_by_family(role_rows)
    planned: list[dict[str, Any]] = []
    per_slice_counts: Counter = Counter()
    for row in manifest_rows:
        candidate_id = str(row.get("candidate_id") or "")
        family = str(row.get("mutation_family") or "")
        role = str(roles.get(family, {}).get("role") or "unknown")
        slice_role = _slice_role_for_manifest_row(row, role)
        if slice_role == "excluded":
            continue
        if per_slice_counts[slice_role] >= max(0, int(max_per_slice)):
            continue
        planned.append(
            {
                "candidate_id": candidate_id,
                "family": family,
                "slice_role": slice_role,
                "family_role": role,
                "split": str(row.get("split") or ""),
                "repeatability_class": str(row.get("repeatability_class") or ""),
                "recommended_reporting": _recommended_reporting(slice_role),
            }
        )
        per_slice_counts[slice_role] += 1
    slice_counts = Counter(row["slice_role"] for row in planned)
    summary = {
        "version": "v0.27.9",
        "status": "PASS" if planned else "REVIEW",
        "analysis_scope": "benchmark_slice_plan",
        "role_registry_artifact": str(DEFAULT_ROLE_REGISTRY.relative_to(REPO_ROOT)),
        "manifest_artifact": str(DEFAULT_MANIFEST.relative_to(REPO_ROOT)),
        "planned_case_count": len(planned),
        "slice_counts": dict(sorted(slice_counts.items())),
        "max_per_slice": int(max_per_slice),
        "mixed_pass_rate_allowed": False,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": "slice_plan_ready_for_role_separated_runner" if planned else "slice_plan_needs_review",
        "next_focus": "run_role_separated_live_slices_or_export_as_benchmark_plan",
    }
    return planned, summary


def _recommended_reporting(slice_role: str) -> str:
    if slice_role == "capability_baseline":
        return "report_pass_rate_and_true_multi_turn_for_capability_only"
    if slice_role == "hard_negative":
        return "report_failure_mode_and_stall_rate_not_default_pass_rate"
    if slice_role == "diagnostic":
        return "report_by_family_and_failure_mode_not_mixed_pass_rate"
    return "do_not_report"


def run_benchmark_slice_plan(
    *,
    role_registry_path: Path = DEFAULT_ROLE_REGISTRY,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT_DIR,
    max_per_slice: int = 3,
) -> dict[str, Any]:
    planned, summary = build_benchmark_slice_plan(
        role_rows=load_jsonl(role_registry_path),
        manifest_rows=load_jsonl(manifest_path),
        max_per_slice=max_per_slice,
    )
    write_outputs(out_dir=out_dir, planned=planned, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, planned: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "slice_plan.jsonl").open("w", encoding="utf-8") as fh:
        for row in planned:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
