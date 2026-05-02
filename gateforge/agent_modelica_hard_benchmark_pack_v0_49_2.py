from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CALIBRATION = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_42_3" / "summary.json"
DEFAULT_REPEATABILITY = REPO_ROOT / "artifacts" / "hard_candidate_repeatability_v0_49_1" / "repeatability_registry.jsonl"
DEFAULT_DIFFICULTY = REPO_ROOT / "artifacts" / "hard_core_adjacent_difficulty_summary_v0_48_7" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_benchmark_pack_v0_49_2"


def build_hard_benchmark_pack(
    *,
    calibration_summary: dict[str, Any],
    repeatability_registry: list[dict[str, Any]],
    difficulty_summary: dict[str, Any],
    version: str = "v0.49.2",
) -> dict[str, Any]:
    existing = [str(case_id) for case_id in calibration_summary.get("formal_hard_negative_case_ids") or []]
    new_cases = [
        str(seed.get("case_id") or "")
        for seed in repeatability_registry
        if str(seed.get("registry_status") or "") == "repeatable_candidate"
    ]
    unstable = [
        str(row.get("case_id") or "")
        for row in difficulty_summary.get("results") or []
        if str(row.get("difficulty_bucket") or "") == "unstable"
    ]
    easy = [
        str(row.get("case_id") or "")
        for row in difficulty_summary.get("results") or []
        if str(row.get("difficulty_bucket") or "") == "easy"
    ]
    hard_pack = sorted(set(existing + new_cases))
    return {
        "version": version,
        "analysis_scope": "hard_benchmark_pack",
        "status": "PASS" if hard_pack else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(hard_pack),
        "existing_hard_count": len(existing),
        "new_hard_count": len(new_cases),
        "hard_pack_count": len(hard_pack),
        "hard_case_ids": hard_pack,
        "unstable_case_ids": sorted(unstable),
        "easy_calibration_case_ids": sorted(easy),
        "decision": "use_hard_pack_for_next_benchmark_or_agent_comparison",
    }


def run_hard_benchmark_pack(
    *,
    calibration_path: Path = DEFAULT_CALIBRATION,
    repeatability_path: Path = DEFAULT_REPEATABILITY,
    difficulty_path: Path = DEFAULT_DIFFICULTY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_hard_benchmark_pack(
        calibration_summary=load_json(calibration_path),
        repeatability_registry=load_jsonl(repeatability_path),
        difficulty_summary=load_json(difficulty_path),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "hard_case_ids.txt").write_text("\n".join(summary["hard_case_ids"]) + "\n", encoding="utf-8")
    return summary
