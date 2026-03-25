"""Release preflight gate for v0.1.8.

Extends the v0.1.7 gate (Incremental Gate Composition Pattern) with checks
specific to the L2 Plan/Replan Engine extraction:

  1. L2 import symmetry  – every public function in
     ``agent_modelica_l2_plan_replan_engine_v1`` is re-exported from the
     executor with the expected ``_`` alias (or as a module-level name).
  2. Executor line-count gate  – executor must be under 2,600 lines
     (tightened from 3,000 after L2 extraction).
  3. L2 test coverage  – the L2 test file exists and covers key function names.
  4. v0.1.7 gate continuity  – all v0.1.7 checks still pass.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pathlib
from datetime import datetime, timezone


SCHEMA_VERSION = "agent_modelica_release_preflight_v0_1_8_evidence_v1"

_REPO_ROOT = pathlib.Path(__file__).parent.parent

# Public names exported from the L2 engine module.
_L2_PUBLIC_NAMES = [
    "MULTISTEP_PLANNER_CONTRACT_VERSION",
    "behavioral_robustness_source_mode",
    "bootstrap_env_from_repo",
    "build_source_blind_multistep_planner_contract",
    "build_source_blind_multistep_planner_prompt",
    "gemini_repair_model_text",
    "llm_generate_repair_plan",
    "llm_repair_model_text",
    "llm_round_constraints",
    "openai_repair_model_text",
    "parse_env_assignment",
    "planner_adapter_for_provider",
    "planner_family_for_provider",
    "resolve_llm_provider",
    "send_with_budget",
]


def _load_json(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str, payload: dict) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _l2_import_symmetry_status() -> tuple[str, list[str], dict]:
    """Check that all L2 public names are re-exported from the executor."""
    reasons: list[str] = []
    try:
        import gateforge.agent_modelica_l2_plan_replan_engine_v1 as l2_mod
        import gateforge.agent_modelica_live_executor_gemini_v1 as exec_mod
    except ImportError as e:
        return "FAIL", [f"import_error:{e}"], {"missing": [], "checked": 0}

    l2_exported = [name for name in dir(l2_mod) if not name.startswith("_") or name == "MULTISTEP_PLANNER_CONTRACT_VERSION"]
    exec_names = set(dir(exec_mod))

    missing = []
    for name in _L2_PUBLIC_NAMES:
        # Accept either the public name or the underscore-aliased name in executor
        alias = f"_{name}"
        if name not in exec_names and alias not in exec_names:
            missing.append(name)

    if missing:
        reasons.append(f"missing_in_executor:{','.join(missing)}")
        status = "FAIL"
    else:
        status = "PASS"

    return status, reasons, {
        "missing": missing,
        "checked": len(_L2_PUBLIC_NAMES),
        "l2_exported": sorted(l2_exported),
    }


def _executor_line_count_status(max_lines: int = 2600) -> tuple[str, list[str], dict]:
    executor_path = _REPO_ROOT / "gateforge" / "agent_modelica_live_executor_gemini_v1.py"
    reasons: list[str] = []
    if not executor_path.exists():
        return "FAIL", ["executor_file_missing"], {"line_count": 0, "max_lines": max_lines}
    line_count = len(executor_path.read_text(encoding="utf-8").splitlines())
    if line_count >= max_lines:
        reasons.append(f"executor_line_count_too_high:{line_count}>={max_lines}")
        return "FAIL", reasons, {"line_count": line_count, "max_lines": max_lines}
    return "PASS", reasons, {"line_count": line_count, "max_lines": max_lines}


def _l2_test_coverage_status() -> tuple[str, list[str], dict]:
    """Check that the L2 test file covers key function names."""
    test_path = _REPO_ROOT / "tests" / "test_agent_modelica_l2_plan_replan_engine_v1.py"
    reasons: list[str] = []
    key_names = [
        "resolve_llm_provider",
        "planner_family_for_provider",
        "build_source_blind_multistep_planner_contract",
        "llm_round_constraints",
        "gemini_repair_model_text",
        "openai_repair_model_text",
        "parse_env_assignment",
    ]
    if not test_path.exists():
        return "FAIL", ["l2_test_file_missing"], {"covered": [], "uncovered": key_names}
    content = test_path.read_text(encoding="utf-8")
    covered = [name for name in key_names if name in content]
    uncovered = [name for name in key_names if name not in content]
    if uncovered:
        reasons.append(f"uncovered_functions:{','.join(uncovered)}")
        return "NEEDS_REVIEW", reasons, {"covered": covered, "uncovered": uncovered}
    return "PASS", reasons, {"covered": covered, "uncovered": uncovered}


def _v017_gate_continuity_status() -> tuple[str, list[str], dict]:
    """Re-run key v0.1.7 checks (OMC symmetry, executor line count, test coverage)."""
    reasons: list[str] = []
    try:
        from gateforge.agent_modelica_release_preflight_v0_1_7_evidence import (
            _omc_import_symmetry_status,
            _omc_test_coverage_status,
        )
    except ImportError as e:
        return "FAIL", [f"v017_import_error:{e}"], {}

    omc_sym_status, omc_sym_reasons, _ = _omc_import_symmetry_status()
    omc_cov_status, omc_cov_reasons, _ = _omc_test_coverage_status()

    details: dict = {
        "v017_omc_import_symmetry": omc_sym_status,
        "v017_omc_test_coverage": omc_cov_status,
    }

    if omc_sym_status != "PASS":
        reasons.append(f"v017_omc_import_symmetry_regressed:{omc_sym_reasons}")
    if omc_cov_status not in {"PASS", "NEEDS_REVIEW"}:
        reasons.append(f"v017_omc_test_coverage_regressed:{omc_cov_reasons}")

    status = "FAIL" if reasons else "PASS"
    details["reasons"] = reasons
    return status, reasons, details


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.1.8 release preflight evidence gate")
    parser.add_argument("--summary", required=True, help="Path to base release summary JSON")
    parser.add_argument("--out", help="Output path (defaults to --summary path)")
    args = parser.parse_args()

    out_path = str(args.out or args.summary)
    summary = _load_json(args.summary)

    sym_status, sym_reasons, sym_details = _l2_import_symmetry_status()
    lc_status, lc_reasons, lc_details = _executor_line_count_status()
    cov_status, cov_reasons, cov_details = _l2_test_coverage_status()
    cont_status, cont_reasons, cont_details = _v017_gate_continuity_status()

    payload = dict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    payload["v018_l2_import_symmetry_status"] = sym_status
    payload["v018_l2_import_symmetry"] = {**sym_details, "reasons": sym_reasons}

    payload["v018_executor_line_count_status"] = lc_status
    payload["v018_executor_line_count"] = {**lc_details, "reasons": lc_reasons}

    payload["v018_l2_test_coverage_status"] = cov_status
    payload["v018_l2_test_coverage"] = {**cov_details, "reasons": cov_reasons}

    payload["v018_v017_gate_continuity_status"] = cont_status
    payload["v018_v017_gate_continuity"] = {**cont_details, "reasons": cont_reasons}

    reasons: list[str] = []
    blocking = [sym_status, lc_status, cont_status]
    for label, status in [
        ("v018_l2_import_symmetry", sym_status),
        ("v018_executor_line_count", lc_status),
        ("v018_v017_gate_continuity", cont_status),
    ]:
        if status != "PASS":
            reasons.append(f"{label}_not_pass")
    if cov_status == "NEEDS_REVIEW":
        reasons.append("v018_l2_test_coverage_needs_review")
    elif cov_status == "FAIL":
        reasons.append("v018_l2_test_coverage_fail")
    payload["reasons"] = reasons

    status = "PASS"
    if any(s == "FAIL" for s in blocking):
        status = "FAIL"
    if cov_status == "FAIL":
        status = "FAIL"
    if status == "PASS" and cov_status == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"
    payload["status"] = status

    _write_json(out_path, payload)
    print(json.dumps(payload, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
