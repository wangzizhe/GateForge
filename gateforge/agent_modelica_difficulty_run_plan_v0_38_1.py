from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_run_plan_v0_38_1"


def build_difficulty_run_plan(
    calibration_summary: dict[str, Any],
    *,
    max_needs_baseline: int = 12,
    version: str = "v0.38.1",
) -> dict[str, Any]:
    rows = list(calibration_summary.get("results") or [])
    formal_hard = [row for row in rows if row.get("difficulty_bucket") == "hard_negative"]
    priors = [row for row in rows if row.get("difficulty_bucket") == "known_hard_prior"]
    needs_baseline = [row for row in rows if row.get("difficulty_bucket") == "needs_baseline"]
    invalid = [row for row in rows if row.get("difficulty_bucket") == "invalid"]

    selected_needs_baseline = needs_baseline[: max(0, int(max_needs_baseline))]
    planned_cases = [
        *[
            {
                "case_id": row["case_id"],
                "family": row["family"],
                "run_reason": "confirm_formal_hard_negative",
                "recommended_repeats": 1,
            }
            for row in formal_hard
        ],
        *[
            {
                "case_id": row["case_id"],
                "family": row["family"],
                "run_reason": "convert_known_hard_prior_to_repeatability",
                "recommended_repeats": 1,
            }
            for row in priors
        ],
        *[
            {
                "case_id": row["case_id"],
                "family": row["family"],
                "run_reason": "initial_baseline_difficulty_probe",
                "recommended_repeats": 1,
            }
            for row in selected_needs_baseline
        ],
    ]
    return {
        "version": version,
        "analysis_scope": "difficulty_run_plan",
        "status": "PASS" if planned_cases else "REVIEW",
        "planned_case_count": len(planned_cases),
        "formal_hard_negative_count": len(formal_hard),
        "known_hard_prior_count": len(priors),
        "needs_baseline_total_count": len(needs_baseline),
        "needs_baseline_selected_count": len(selected_needs_baseline),
        "invalid_excluded_count": len(invalid),
        "invalid_excluded_case_ids": [row["case_id"] for row in invalid],
        "planned_cases": planned_cases,
        "run_contract": {
            "tool_profile": "base",
            "run_mode": "tool_use",
            "max_token_budget": 32000,
            "fixed_provider_from_env": True,
            "evidence_role": "formal_experiment",
            "provider_smoke_required": True,
            "wrapper_repair_allowed": False,
        },
        "scope_note": (
            "This plan schedules baseline difficulty calibration. It excludes prompt-leaking cases and does not "
            "add tools, hints, routing, or wrapper repair."
        ),
    }


def write_difficulty_run_plan_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

