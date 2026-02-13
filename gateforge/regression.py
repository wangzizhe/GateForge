from __future__ import annotations

import json
from pathlib import Path

from .checkers import run_checkers


def compare_evidence(
    baseline: dict,
    candidate: dict,
    runtime_regression_threshold: float = 0.2,
    strict: bool = False,
    strict_model_script: bool = False,
    checker_names: list[str] | None = None,
) -> dict:
    reasons: list[str] = []

    if strict:
        if baseline.get("schema_version") != candidate.get("schema_version"):
            reasons.append("strict_schema_version_mismatch")
        if baseline.get("backend") != candidate.get("backend"):
            reasons.append("strict_backend_mismatch")
        if strict_model_script and baseline.get("model_script") != candidate.get("model_script"):
            reasons.append("strict_model_script_mismatch")

    if candidate.get("status") != "success":
        reasons.append("candidate_status_not_success")
    if candidate.get("gate") != "PASS":
        reasons.append("candidate_gate_not_pass")
    if baseline.get("check_ok") and not candidate.get("check_ok"):
        reasons.append("check_regression")
    if baseline.get("simulate_ok") and not candidate.get("simulate_ok"):
        reasons.append("simulate_regression")

    base_runtime = float(baseline.get("metrics", {}).get("runtime_seconds", 0.0))
    cand_runtime = float(candidate.get("metrics", {}).get("runtime_seconds", 0.0))
    if base_runtime > 0:
        allowed = base_runtime * (1 + runtime_regression_threshold)
        if cand_runtime > allowed:
            reasons.append(
                f"runtime_regression:{cand_runtime:.4f}s>{allowed:.4f}s"
            )

    checker_findings, checker_reasons = run_checkers(
        baseline=baseline,
        candidate=candidate,
        checker_names=checker_names,
    )
    reasons.extend([r for r in checker_reasons if r not in reasons])

    decision = "FAIL" if reasons else "PASS"
    return {
        "decision": decision,
        "proposal_id": candidate.get("proposal_id") or baseline.get("proposal_id"),
        "strict": strict,
        "strict_model_script": strict_model_script,
        "baseline_run_id": baseline.get("run_id"),
        "candidate_run_id": candidate.get("run_id"),
        "runtime_threshold": runtime_regression_threshold,
        "baseline_runtime_seconds": base_runtime,
        "candidate_runtime_seconds": cand_runtime,
        "reasons": reasons,
        "findings": checker_findings,
    }


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown(path: str, result: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Regression Report",
        "",
        f"- decision: `{result['decision']}`",
        f"- proposal_id: `{result.get('proposal_id')}`",
        f"- strict: `{result['strict']}`",
        f"- strict_model_script: `{result['strict_model_script']}`",
        f"- baseline_run_id: `{result['baseline_run_id']}`",
        f"- candidate_run_id: `{result['candidate_run_id']}`",
        f"- baseline_runtime_seconds: `{result['baseline_runtime_seconds']}`",
        f"- candidate_runtime_seconds: `{result['candidate_runtime_seconds']}`",
        f"- runtime_threshold: `{result['runtime_threshold']}`",
        "",
        "## Reasons",
        "",
    ]
    if result["reasons"]:
        lines.extend([f"- `{r}`" for r in result["reasons"]])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Checker Findings", ""])
    findings = result.get("findings", [])
    if findings:
        for finding in findings:
            lines.append(
                f"- `{finding.get('checker')}` `{finding.get('severity')}` `{finding.get('reason')}`: {finding.get('message')}"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
