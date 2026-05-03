from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "external_agent_result_intake_v0_50_3"

REQUIRED_RESULT_FIELDS = (
    "case_id",
    "agent_name",
    "llm_model",
    "final_verdict",
    "omc_invocation_count",
    "submitted",
    "failure_category",
)


def validate_external_agent_result(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_RESULT_FIELDS:
        if field not in row:
            errors.append(f"missing:{field}")
    verdict = str(row.get("final_verdict") or "")
    if verdict and verdict not in {"PASS", "FAIL", "PROVIDER_ERROR", "INVALID_RUN"}:
        errors.append(f"invalid_final_verdict:{verdict}")
    if "omc_invocation_count" in row and int(row.get("omc_invocation_count") or 0) < 0:
        errors.append("negative_omc_invocation_count")
    return errors


def build_external_agent_result_intake_summary(
    *,
    rows: list[dict[str, Any]],
    version: str = "v0.50.3",
) -> dict[str, Any]:
    validation_errors: dict[str, list[str]] = {}
    for idx, row in enumerate(rows):
        errors = validate_external_agent_result(row)
        if errors:
            validation_errors[str(row.get("case_id") or f"row_{idx}")] = errors
    pass_count = sum(1 for row in rows if row.get("final_verdict") == "PASS")
    return {
        "version": version,
        "analysis_scope": "external_agent_result_intake",
        "status": "PASS" if rows and not validation_errors else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "result_count": len(rows),
        "pass_count": pass_count,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
        "required_result_fields": list(REQUIRED_RESULT_FIELDS),
    }


def write_external_agent_result_intake_template(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    template = {
        "case_id": "",
        "agent_name": "",
        "llm_model": "",
        "final_verdict": "",
        "omc_invocation_count": 0,
        "submitted": False,
        "failure_category": "",
        "trajectory_path": "",
        "notes": "",
    }
    (out_dir / "result_template.json").write_text(json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = build_external_agent_result_intake_summary(rows=[])
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
