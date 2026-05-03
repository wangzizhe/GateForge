from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULT_PATHS = (
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_smoke_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_batch2_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_batch3_v0_48_5" / "results.jsonl",
    REPO_ROOT / "artifacts" / "hard_core_adjacent_baseline_batch4_v0_48_5" / "results.jsonl",
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_comparison_baseline_summary_v0_50_1"


def _latest_rows_by_case(paths: tuple[Path, ...]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if case_id:
                rows[case_id] = row
    return rows


def build_gateforge_comparison_baseline_summary(
    *,
    result_paths: tuple[Path, ...] = DEFAULT_RESULT_PATHS,
    version: str = "v0.50.1",
) -> dict[str, Any]:
    rows = _latest_rows_by_case(result_paths)
    pass_cases = sorted(case_id for case_id, row in rows.items() if row.get("final_verdict") == "PASS")
    fail_cases = sorted(case_id for case_id, row in rows.items() if row.get("final_verdict") != "PASS")
    provider_errors = sorted(case_id for case_id, row in rows.items() if row.get("provider_error"))
    return {
        "version": version,
        "analysis_scope": "gateforge_comparison_baseline_summary",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(rows and not provider_errors),
        "case_count": len(rows),
        "pass_count": len(pass_cases),
        "fail_count": len(fail_cases),
        "provider_error_count": len(provider_errors),
        "pass_case_ids": pass_cases,
        "fail_case_ids": fail_cases,
        "provider_error_case_ids": provider_errors,
        "baseline_scope_note": "This summarizes existing GateForge base tool-use evidence for comparison setup only.",
    }


def write_gateforge_comparison_baseline_summary_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_gateforge_comparison_baseline_summary(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = build_gateforge_comparison_baseline_summary()
    write_gateforge_comparison_baseline_summary_outputs(out_dir=out_dir, summary=summary)
    return summary
