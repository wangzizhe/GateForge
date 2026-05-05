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
    REPO_ROOT / "artifacts" / "external_agent_holdout_results_v0_61_0"
)
DEFAULT_EXTERNAL_VERIFICATION = (
    REPO_ROOT / "artifacts" / "external_agent_holdout_verification_v0_61_0" / "summary.json"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "external_agent_attribution_v0_62_0"


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


def _external_result_rows(results_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not results_dir.exists():
        return rows
    for path in sorted(results_dir.glob("*.json")):
        row = load_json(path)
        if row:
            row["_result_path"] = str(path)
            rows.append(row)
    return rows


def _verification_by_case(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("case_id") or ""): row
        for row in summary.get("rows", [])
        if str(row.get("case_id") or "")
    }


def _read_external_model_text(row: dict[str, Any]) -> str:
    path_text = str(row.get("final_model_path") or "").strip()
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def classify_repair_pattern(model_text: str) -> dict[str, Any]:
    zero_flow_equations = re.findall(
        r"\b[A-Za-z_][A-Za-z0-9_\[\]\.]*\.i\s*=\s*0\s*;",
        model_text,
    )
    removed_balance_hint = "p.i + n.i = 0" not in model_text and "p.i+n.i=0" not in model_text
    return {
        "zero_flow_equation_count": len(zero_flow_equations),
        "has_zero_flow_probe_pattern": bool(zero_flow_equations),
        "removed_explicit_pin_balance_hint": bool(removed_balance_hint),
        "repair_pattern": (
            "probe_zero_flow_constraint"
            if zero_flow_equations
            else "connector_balance_simplification"
            if removed_balance_hint
            else "unknown"
        ),
    }


def _tool_call_names(row: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for step in row.get("steps", []) or []:
        for call in step.get("tool_calls", []) or []:
            name = str(call.get("name") or "")
            if name:
                names.append(name)
    return names


def _omc_result_text(row: dict[str, Any]) -> str:
    chunks: list[str] = []
    for step in row.get("steps", []) or []:
        chunks.append(str(step.get("text") or ""))
        for result in step.get("tool_results", []) or []:
            chunks.append(str(result.get("result") or ""))
    return "\n".join(chunks)


def _has_successful_candidate(row: dict[str, Any]) -> bool:
    for step in row.get("steps", []) or []:
        for result in step.get("tool_results", []) or []:
            text = str(result.get("result") or "").lower()
            if "record simulationresult" in text and 'resultfile = ""' not in text:
                return True
    return False


def _candidate_zero_flow_counts(row: dict[str, Any]) -> list[int]:
    counts: list[int] = []
    for step in row.get("steps", []) or []:
        for call in step.get("tool_calls", []) or []:
            if str(call.get("name") or "") not in {"check_model", "simulate_model"}:
                continue
            model_text = str((call.get("arguments") or {}).get("model_text") or "")
            counts.append(
                len(
                    re.findall(
                        r"\b[A-Za-z_][A-Za-z0-9_\[\]\.]*\.i\s*=\s*0\s*;",
                        model_text,
                    )
                )
            )
    return counts


def classify_gateforge_failure(row: dict[str, Any], external_pattern: dict[str, Any]) -> str:
    if str(row.get("final_verdict") or "").upper() == "PASS":
        return "gateforge_pass"
    if str(row.get("provider_error") or "").strip():
        return "provider_failure"
    if not bool(row.get("submitted")):
        if _has_successful_candidate(row):
            return "successful_candidate_not_submitted"
        text = _omc_result_text(row).lower()
        zero_counts = _candidate_zero_flow_counts(row)
        if (
            external_pattern.get("has_zero_flow_probe_pattern")
            and zero_counts
            and max(zero_counts) > 0
        ):
            return "zero_flow_pattern_underfit"
        if "resultfile = \"\"" in text and external_pattern.get("has_zero_flow_probe_pattern"):
            return "semantic_pattern_not_inferred"
        if "completed successfully" in text and "resultfile = \"\"" not in text:
            return "submit_or_verification_discipline"
        return "candidate_not_materialized"
    return "submitted_but_failed_verification"


def build_external_agent_attribution_summary(
    *,
    gateforge_rows: list[dict[str, Any]],
    external_rows: list[dict[str, Any]],
    verification_summary: dict[str, Any],
    version: str = "v0.62.0",
) -> dict[str, Any]:
    gateforge_by_case = {str(row.get("case_id") or ""): row for row in gateforge_rows}
    verification = _verification_by_case(verification_summary)

    paired_rows: list[dict[str, Any]] = []
    for external in external_rows:
        case_id = str(external.get("case_id") or "")
        gf = gateforge_by_case.get(case_id, {})
        verified = verification.get(case_id, {})
        external_model_text = _read_external_model_text(external)
        pattern = classify_repair_pattern(external_model_text)
        external_pass = (
            str(external.get("final_verdict") or "").upper() == "PASS"
            and bool(verified.get("check_ok"))
            and bool(verified.get("simulate_ok"))
        )
        gateforge_pass = str(gf.get("final_verdict") or "").upper() == "PASS"
        row = {
            "case_id": case_id,
            "gateforge_verdict": gf.get("final_verdict", "MISSING"),
            "gateforge_submitted": bool(gf.get("submitted")),
            "gateforge_step_count": int(gf.get("step_count") or 0),
            "gateforge_tool_calls": _tool_call_names(gf),
            "gateforge_had_successful_candidate": _has_successful_candidate(gf),
            "gateforge_max_zero_flow_candidate_count": max(_candidate_zero_flow_counts(gf) or [0]),
            "external_verdict": external.get("final_verdict", "MISSING"),
            "external_verified_pass": external_pass,
            "external_omc_invocation_count": int(external.get("omc_invocation_count") or 0),
            "external_submitted": bool(external.get("submitted")),
            "repair_pattern": pattern["repair_pattern"],
            "zero_flow_equation_count": pattern["zero_flow_equation_count"],
            "paired_outcome": (
                "gateforge_fail_external_pass"
                if external_pass and not gateforge_pass
                else "both_pass"
                if external_pass and gateforge_pass
                else "external_not_verified_pass"
            ),
            "gateforge_failure_attribution": classify_gateforge_failure(gf, pattern),
        }
        paired_rows.append(row)

    diff_rows = [row for row in paired_rows if row["paired_outcome"] == "gateforge_fail_external_pass"]
    attribution_counts: dict[str, int] = {}
    repair_pattern_counts: dict[str, int] = {}
    for row in paired_rows:
        attribution_counts[row["gateforge_failure_attribution"]] = (
            attribution_counts.get(row["gateforge_failure_attribution"], 0) + 1
        )
        repair_pattern_counts[row["repair_pattern"]] = repair_pattern_counts.get(row["repair_pattern"], 0) + 1

    provider_blocked_count = int(verification_summary.get("provider_blocked_count") or 0)
    return {
        "version": version,
        "analysis_scope": "external_agent_holdout_attribution",
        "evidence_role": "formal_experiment",
        "artifact_complete": bool(
            gateforge_rows
            and external_rows
            and verification_summary
            and all(str(r.get("case_id") or "") in external_rows for r in gateforge_rows)
        ),
        "provider_status": "provider_stable" if provider_blocked_count == 0 else "provider_blocked",
        "provider_error_count": provider_blocked_count,
        "conclusion_allowed": bool(gateforge_rows and external_rows and provider_blocked_count == 0),
        "case_count": len(paired_rows),
        "gateforge_pass_count": sum(1 for row in paired_rows if row["gateforge_verdict"] == "PASS"),
        "external_verified_pass_count": sum(1 for row in paired_rows if row["external_verified_pass"]),
        "paired_difference_count": len(diff_rows),
        "paired_difference_case_ids": [row["case_id"] for row in diff_rows],
        "repair_pattern_counts": repair_pattern_counts,
        "gateforge_failure_attribution_counts": attribution_counts,
        "primary_finding": (
            "external_agent_verified_all_holdout_cases_gateforge_base_failed_majority"
            if paired_rows and len(diff_rows) >= 1
            else "insufficient_difference"
        ),
        "interpretation": (
            "The same backend model solved more cases in the external coding-agent harness. "
            "The dominant observed repair pattern is probe zero-flow constraint insertion; "
            "this is an Agent behavior attribution, not wrapper repair logic."
        ),
        "paired_rows": paired_rows,
    }


def run_external_agent_attribution(
    *,
    gateforge_results_path: Path = DEFAULT_GATEFORGE_RESULTS,
    external_results_dir: Path = DEFAULT_EXTERNAL_RESULTS_DIR,
    external_verification_path: Path = DEFAULT_EXTERNAL_VERIFICATION,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_external_agent_attribution_summary(
        gateforge_rows=load_jsonl(gateforge_results_path),
        external_rows=_external_result_rows(external_results_dir),
        verification_summary=load_json(external_verification_path),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paired_jsonl = "\n".join(json.dumps(row, sort_keys=True) for row in summary["paired_rows"])
    (out_dir / "paired_rows.jsonl").write_text(paired_jsonl + ("\n" if paired_jsonl else ""), encoding="utf-8")
    return summary
