from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_provider_stability_gate_v0_36_1 import classify_provider_status


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "difficulty_baseline_summary_v0_38_2"


def build_difficulty_baseline_summary(
    rows: list[dict[str, Any]],
    *,
    provider: str = "",
    model: str = "",
    tool_profile: str = "base",
    version: str = "v0.38.2",
) -> dict[str, Any]:
    provider_errors = [str(row.get("provider_error") or "") for row in rows if str(row.get("provider_error") or "")]
    provider_gate = classify_provider_status(
        provider=provider or str(rows[0].get("provider") or "provider") if rows else provider,
        model=model or "model",
        tool_profile=tool_profile,
        provider_errors=provider_errors,
        tool_use_supported=True,
    )
    valid_rows = [row for row in rows if not str(row.get("provider_error") or "")]
    valid_pass = [row for row in valid_rows if row.get("final_verdict") == "PASS"]
    valid_fail = [row for row in valid_rows if row.get("final_verdict") != "PASS"]
    provider_failed = [row for row in rows if str(row.get("provider_error") or "")]
    conclusion_allowed = bool(provider_gate["conclusion_allowed"]) and len(valid_rows) == len(rows)
    return {
        "version": version,
        "analysis_scope": "difficulty_baseline_summary",
        "status": "PASS" if rows else "REVIEW",
        "evidence_role": "formal_experiment" if conclusion_allowed else "smoke",
        "conclusion_allowed": conclusion_allowed,
        "provider_status": provider_gate["provider_status"],
        "provider_error_count": len(provider_errors),
        "case_count": len(rows),
        "valid_case_count": len(valid_rows),
        "provider_failed_case_count": len(provider_failed),
        "valid_pass_count": len(valid_pass),
        "valid_fail_count": len(valid_fail),
        "valid_pass_case_ids": [str(row.get("case_id") or "") for row in valid_pass],
        "valid_fail_case_ids": [str(row.get("case_id") or "") for row in valid_fail],
        "provider_failed_case_ids": [str(row.get("case_id") or "") for row in provider_failed],
        "provider_error_types": sorted({error.split(":", 1)[0] for error in provider_errors}),
        "provider_gate": provider_gate,
        "scope_note": (
            "Only rows without provider errors can describe Agent behavior. If provider errors occur, the run is "
            "kept as provider smoke/debug evidence and must not be used for full difficulty calibration."
        ),
    }


def write_difficulty_baseline_summary_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_results_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows

