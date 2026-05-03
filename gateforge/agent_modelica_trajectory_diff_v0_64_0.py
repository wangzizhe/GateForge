from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GATEFORGE_RESULTS = (
    REPO_ROOT / "artifacts" / "solvable_holdout_baseline_v0_61_3_stream" / "results.jsonl"
)
DEFAULT_EXTERNAL_RESULTS_DIR = (
    REPO_ROOT / "artifacts" / "external_agent_opencode_holdout_results_v0_61_0"
)
DEFAULT_ATTRIBUTION = REPO_ROOT / "artifacts" / "external_agent_attribution_v0_62_0" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "trajectory_diff_v0_64_0"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def zero_flow_targets(model_text: str) -> list[str]:
    return sorted(
        re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_\[\]\.]*\.i)\s*=\s*0\s*;",
            model_text,
        )
    )


def equation_variable_count(output: str) -> tuple[int | None, int | None]:
    match = re.search(
        r"Class\s+.*?\s+has\s+([0-9]+)\s+equation\(s\)\s+and\s+([0-9]+)\s+variable\(s\)",
        str(output or ""),
    )
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def omc_success(output: str) -> bool:
    text = str(output or "")
    return "record SimulationResult" in text and 'resultFile = ""' not in text


def extract_gateforge_candidate_trace(row: dict[str, Any]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for step in row.get("steps", []) or []:
        calls = step.get("tool_calls", []) or []
        results = step.get("tool_results", []) or []
        for idx, call in enumerate(calls):
            name = str(call.get("name") or "")
            if name not in {"check_model", "simulate_model", "submit_final"}:
                continue
            model_text = str((call.get("arguments") or {}).get("model_text") or "")
            result = str((results[idx] if idx < len(results) else {}).get("result") or "")
            equations, variables = equation_variable_count(result)
            trace.append(
                {
                    "step": step.get("step"),
                    "tool": name,
                    "zero_flow_targets": zero_flow_targets(model_text),
                    "zero_flow_count": len(zero_flow_targets(model_text)),
                    "equation_count": equations,
                    "variable_count": variables,
                    "equation_variable_delta": None
                    if equations is None or variables is None
                    else equations - variables,
                    "omc_success": omc_success(result),
                }
            )
    return trace


def _external_rows(results_dir: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not results_dir.exists():
        return rows
    for path in sorted(results_dir.glob("*.json")):
        row = load_json(path)
        case_id = str(row.get("case_id") or "")
        if case_id:
            rows[case_id] = row
    return rows


def _read_model(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_trajectory_diff_summary(
    *,
    gateforge_rows: list[dict[str, Any]],
    external_rows: dict[str, dict[str, Any]],
    attribution_summary: dict[str, Any],
    version: str = "v0.64.0",
) -> dict[str, Any]:
    paired = {
        str(row.get("case_id") or ""): row
        for row in attribution_summary.get("paired_rows", [])
        if str(row.get("case_id") or "")
    }
    case_rows: list[dict[str, Any]] = []
    for gf in gateforge_rows:
        case_id = str(gf.get("case_id") or "")
        ext = external_rows.get(case_id, {})
        external_model = _read_model(str(ext.get("final_model_path") or ""))
        external_targets = zero_flow_targets(external_model)
        trace = extract_gateforge_candidate_trace(gf)
        first_zero_step = next((row["step"] for row in trace if row["zero_flow_count"] > 0), None)
        first_success_step = next((row["step"] for row in trace if row["omc_success"]), None)
        max_zero = max([row["zero_flow_count"] for row in trace] or [0])
        exact_target_match = any(row["zero_flow_targets"] == external_targets for row in trace)
        case_rows.append(
            {
                "case_id": case_id,
                "paired_outcome": paired.get(case_id, {}).get("paired_outcome", ""),
                "gateforge_verdict": gf.get("final_verdict", ""),
                "gateforge_submitted": bool(gf.get("submitted")),
                "gateforge_first_zero_flow_step": first_zero_step,
                "gateforge_first_success_step": first_success_step,
                "gateforge_max_zero_flow_count": max_zero,
                "gateforge_exact_external_zero_flow_targets_seen": exact_target_match,
                "external_zero_flow_targets": external_targets,
                "external_zero_flow_count": len(external_targets),
                "external_omc_invocation_count": int(ext.get("omc_invocation_count") or 0),
                "attribution": paired.get(case_id, {}).get("gateforge_failure_attribution", ""),
                "candidate_trace": trace,
            }
        )
    diff_rows = [row for row in case_rows if row["paired_outcome"] == "gateforge_fail_external_pass"]
    return {
        "version": version,
        "analysis_scope": "trajectory_diff",
        "evidence_role": "formal_experiment",
        "artifact_complete": bool(gateforge_rows and external_rows and attribution_summary),
        "conclusion_allowed": bool(gateforge_rows and external_rows and attribution_summary),
        "case_count": len(case_rows),
        "paired_difference_count": len(diff_rows),
        "opencode_trace_limitation": "external_agent_full_step_trace_not_available_final_model_and_summary_only",
        "diff_exact_zero_flow_match_count": sum(
            1 for row in diff_rows if row["gateforge_exact_external_zero_flow_targets_seen"]
        ),
        "diff_successful_candidate_not_submitted_count": sum(
            1 for row in diff_rows if row["gateforge_first_success_step"] is not None and not row["gateforge_submitted"]
        ),
        "diff_zero_flow_attempt_without_exact_match_count": sum(
            1
            for row in diff_rows
            if row["gateforge_max_zero_flow_count"] > 0
            and not row["gateforge_exact_external_zero_flow_targets_seen"]
        ),
        "diff_no_zero_flow_attempt_count": sum(
            1 for row in diff_rows if row["gateforge_max_zero_flow_count"] == 0
        ),
        "case_rows": case_rows,
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "wrapper_auto_submit_added": False,
        },
    }


def run_trajectory_diff(
    *,
    gateforge_results_path: Path = DEFAULT_GATEFORGE_RESULTS,
    external_results_dir: Path = DEFAULT_EXTERNAL_RESULTS_DIR,
    attribution_path: Path = DEFAULT_ATTRIBUTION,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_trajectory_diff_summary(
        gateforge_rows=load_jsonl(gateforge_results_path),
        external_rows=_external_rows(external_results_dir),
        attribution_summary=load_json(attribution_path),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = "\n".join(json.dumps(row, sort_keys=True) for row in summary["case_rows"])
    (out_dir / "case_rows.jsonl").write_text(rows + ("\n" if rows else ""), encoding="utf-8")
    return summary
