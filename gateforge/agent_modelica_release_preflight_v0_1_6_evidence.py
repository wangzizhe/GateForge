"""Release preflight gate for v0.1.6.

Extends the v0.1.5 gate pattern (Incremental Gate Composition Pattern)
with checks specific to the L4 Guided Search Engine extraction and the
Behavioral Contract Evaluator extraction:

  1. L4 import symmetry  – every public function in the L4 module is
     re-exported from the executor with the expected ``_`` alias.
  2. Executor line-count gate  – executor must be under 3,200 lines
     (tightened from 4,000 after BC extraction).
  3. L4 test coverage  – the L4 test file exists and covers the main
     function names.
  4. L4 search determinism  – ``build_adaptive_search_candidates``
     produces identical output on repeated calls with identical inputs.
  5. BC import symmetry  – every public function in the Behavioral
     Contract Evaluator module is re-exported from the executor.
  6. BC test coverage  – the BC test file exists and covers the main
     function names.
  7. v0.1.5 gate continuity  – existing gate checks (v4 replan, v5
     branch choice, v5 guided search, L5 trend) still pass.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pathlib
from datetime import datetime, timezone


SCHEMA_VERSION = "agent_modelica_release_preflight_v0_1_6_evidence_v2"

_REPO_ROOT = pathlib.Path(__file__).parent.parent

# All public names exported from the BC (Behavioral Contract Evaluator) module.
_BC_PUBLIC_NAMES = [
    "apply_initialization_marker_repair",
    "evaluate_behavioral_contract_from_model_text",
    "normalize_behavioral_contract_text",
]

# All public names exported from the L4 module (no leading _).
_L4_PUBLIC_NAMES = [
    "adaptive_parameter_target_pools",
    "apply_behavioral_robustness_source_blind_local_repair",
    "apply_source_blind_multistep_branch_escape_search",
    "apply_source_blind_multistep_exposure_repair",
    "apply_source_blind_multistep_llm_plan",
    "apply_source_blind_multistep_llm_resolution",
    "apply_source_blind_multistep_local_search",
    "apply_source_blind_multistep_stage2_local_repair",
    "behavioral_robustness_local_repair_clusters",
    "build_adaptive_search_candidates",
    "build_guided_search_execution_plan",
    "build_guided_search_observation_payload",
    "guard_robustness_patch",
    "llm_plan_branch_match",
    "llm_plan_parameter_match",
    "normalize_source_blind_multistep_llm_plan",
    "preferred_llm_parameter_order_for_branch",
    "resolve_llm_plan_parameter_names",
    "robustness_structure_signature",
    "select_initial_llm_plan_parameters",
    "source_blind_multistep_branch_escape_templates",
    "source_blind_multistep_exposure_clusters",
    "source_blind_multistep_llm_resolution_targets",
    "source_blind_multistep_local_search_templates",
    "source_blind_multistep_stage2_resolution_clusters",
]


def _load_json(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _status_ok(value: str) -> bool:
    return str(value or "").strip().upper() == "PASS"


# ---------------------------------------------------------------------------
# L4 import symmetry
# ---------------------------------------------------------------------------


def _l4_import_symmetry_status() -> tuple[str, list[str], dict]:
    """Verify every L4 public name is re-exported from executor with _ prefix."""
    reasons: list[str] = []
    missing: list[str] = []
    try:
        executor = importlib.import_module("gateforge.agent_modelica_live_executor_gemini_v1")
        l4 = importlib.import_module("gateforge.agent_modelica_l4_guided_search_engine_v1")
    except ImportError as exc:
        return "FAIL", [f"import_error:{exc}"], {"missing": [], "checked": 0}

    # apply_behavioral_robustness_source_blind_local_repair is a thin
    # wrapper in the executor (passes env vars), not a direct alias —
    # so only check presence, not object identity for that one.
    _WRAPPER_ONLY = {"apply_behavioral_robustness_source_blind_local_repair"}
    l4_names = {
        name
        for name, _ in inspect.getmembers(l4, inspect.isfunction)
        if not name.startswith("_")
    }
    for name in _L4_PUBLIC_NAMES:
        alias = f"_{name}"
        if not hasattr(executor, alias):
            missing.append(name)
        elif name not in _WRAPPER_ONLY and getattr(executor, alias) is not getattr(l4, name, None):
            missing.append(f"{name}(alias_mismatch)")
    if missing:
        reasons.append(f"l4_alias_missing:{','.join(missing)}")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {"missing": missing, "checked": len(_L4_PUBLIC_NAMES), "l4_exported": sorted(l4_names)},
    )


# ---------------------------------------------------------------------------
# Executor line count
# ---------------------------------------------------------------------------


def _executor_line_count_status(max_lines: int = 3200) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    executor_path = _REPO_ROOT / "gateforge" / "agent_modelica_live_executor_gemini_v1.py"
    if not executor_path.exists():
        return "FAIL", ["executor_file_missing"], {"line_count": 0, "max_lines": max_lines}
    line_count = sum(1 for _ in executor_path.open(encoding="utf-8"))
    if line_count >= max_lines:
        reasons.append(f"executor_line_count_too_high:{line_count}>={max_lines}")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {"line_count": line_count, "max_lines": max_lines},
    )


# ---------------------------------------------------------------------------
# L4 test coverage
# ---------------------------------------------------------------------------


def _l4_test_coverage_status() -> tuple[str, list[str], dict]:
    """Check the L4 test file exists and mentions the key function names."""
    reasons: list[str] = []
    test_path = _REPO_ROOT / "tests" / "test_agent_modelica_l4_guided_search_engine_v1.py"
    if not test_path.exists():
        return "FAIL", ["l4_test_file_missing"], {"covered": [], "uncovered": _L4_PUBLIC_NAMES}
    content = test_path.read_text(encoding="utf-8")
    uncovered = [name for name in _L4_PUBLIC_NAMES if name not in content]
    if uncovered:
        reasons.append(f"l4_test_coverage_gap:{','.join(uncovered)}")
    return (
        "PASS" if not reasons else "NEEDS_REVIEW",
        reasons,
        {"covered": [n for n in _L4_PUBLIC_NAMES if n in content], "uncovered": uncovered},
    )


# ---------------------------------------------------------------------------
# L4 search determinism
# ---------------------------------------------------------------------------


def _l4_search_determinism_status() -> tuple[str, list[str], dict]:
    """Verify adaptive search candidate generation is deterministic."""
    reasons: list[str] = []
    try:
        from gateforge.agent_modelica_l4_guided_search_engine_v1 import build_adaptive_search_candidates
    except ImportError as exc:
        return "FAIL", [f"import_error:{exc}"], {"deterministic": False}

    text = "model PlantB\n  parameter Real height = 1.2;\n  parameter Real duration = 1.1;\nend PlantB;"
    kwargs = dict(
        current_text=text,
        failure_type="stability_then_behavior",
        current_stage="stage_1",
        current_fail_bucket="",
        search_memory={},
        search_kind="stage_1_unlock",
    )
    result_a = build_adaptive_search_candidates(**kwargs)
    result_b = build_adaptive_search_candidates(**kwargs)

    keys_a = [c.get("candidate_key") for c in result_a]
    keys_b = [c.get("candidate_key") for c in result_b]
    deterministic = keys_a == keys_b
    if not deterministic:
        reasons.append("l4_search_non_deterministic")
    return (
        "PASS" if deterministic else "FAIL",
        reasons,
        {"deterministic": deterministic, "candidate_count": len(result_a)},
    )


# ---------------------------------------------------------------------------
# BC import symmetry
# ---------------------------------------------------------------------------


def _bc_import_symmetry_status() -> tuple[str, list[str], dict]:
    """Verify every BC public name is re-exported from executor with _ prefix."""
    reasons: list[str] = []
    missing: list[str] = []
    try:
        executor = importlib.import_module("gateforge.agent_modelica_live_executor_gemini_v1")
        bc = importlib.import_module("gateforge.agent_modelica_behavioral_contract_evaluator_v1")
    except ImportError as exc:
        return "FAIL", [f"import_error:{exc}"], {"missing": [], "checked": 0}

    bc_names = {
        name
        for name, _ in inspect.getmembers(bc, inspect.isfunction)
        if not name.startswith("_")
    }
    for name in _BC_PUBLIC_NAMES:
        alias = f"_{name}"
        if not hasattr(executor, alias):
            missing.append(name)
        elif getattr(executor, alias) is not getattr(bc, name, None):
            missing.append(f"{name}(alias_mismatch)")
    if missing:
        reasons.append(f"bc_alias_missing:{','.join(missing)}")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {"missing": missing, "checked": len(_BC_PUBLIC_NAMES), "bc_exported": sorted(bc_names)},
    )


# ---------------------------------------------------------------------------
# BC test coverage
# ---------------------------------------------------------------------------


def _bc_test_coverage_status() -> tuple[str, list[str], dict]:
    """Check the BC test file exists and mentions the key function names."""
    reasons: list[str] = []
    test_path = _REPO_ROOT / "tests" / "test_agent_modelica_behavioral_contract_evaluator_v1.py"
    if not test_path.exists():
        return "FAIL", ["bc_test_file_missing"], {"covered": [], "uncovered": _BC_PUBLIC_NAMES}
    content = test_path.read_text(encoding="utf-8")
    uncovered = [name for name in _BC_PUBLIC_NAMES if name not in content]
    if uncovered:
        reasons.append(f"bc_test_coverage_gap:{','.join(uncovered)}")
    return (
        "PASS" if not reasons else "NEEDS_REVIEW",
        reasons,
        {"covered": [n for n in _BC_PUBLIC_NAMES if n in content], "uncovered": uncovered},
    )


# ---------------------------------------------------------------------------
# v0.1.5 gate continuity (re-use logic from the v0.1.5 module)
# ---------------------------------------------------------------------------


def _l5_trend_status(l5_trend: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    authority_status = str(l5_trend.get("authority_status") or "").strip()
    if not l5_trend:
        reasons.append("l5_trend_summary_missing")
    elif authority_status == "insufficient_data":
        reasons.append("l5_trend_authority_insufficient_data")
    elif authority_status == "calibrating":
        reasons.append("l5_trend_authority_calibrating")
    status = "PASS" if not reasons else "NEEDS_REVIEW"
    return (
        status,
        reasons,
        {
            "authority_status": authority_status,
            "baseline_derived_pct": l5_trend.get("baseline_derived_pct"),
            "volatility_pp": l5_trend.get("volatility_pp"),
            "trend_direction": l5_trend.get("trend_direction"),
        },
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.1.6 release preflight evidence gate")
    parser.add_argument("--summary", required=True, help="Path to the base release summary JSON")
    parser.add_argument("--l5-performance-trend", default=None,
                        help="Optional path to l5_performance_trend.json")
    parser.add_argument("--out", help="Output path (defaults to --summary path)")
    args = parser.parse_args()

    out_path = str(args.out or args.summary)
    summary = _load_json(args.summary)
    l5_trend = _load_json(args.l5_performance_trend) if args.l5_performance_trend else {}

    sym_status, sym_reasons, sym_details = _l4_import_symmetry_status()
    lc_status, lc_reasons, lc_details = _executor_line_count_status()
    cov_status, cov_reasons, cov_details = _l4_test_coverage_status()
    det_status, det_reasons, det_details = _l4_search_determinism_status()
    bc_sym_status, bc_sym_reasons, bc_sym_details = _bc_import_symmetry_status()
    bc_cov_status, bc_cov_reasons, bc_cov_details = _bc_test_coverage_status()
    l5_status, l5_reasons, l5_details = _l5_trend_status(l5_trend)

    payload = dict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    payload["v016_l4_import_symmetry_status"] = sym_status
    payload["v016_l4_import_symmetry"] = {**sym_details, "reasons": sym_reasons}

    payload["v016_executor_line_count_status"] = lc_status
    payload["v016_executor_line_count"] = {**lc_details, "reasons": lc_reasons}

    payload["v016_l4_test_coverage_status"] = cov_status
    payload["v016_l4_test_coverage"] = {**cov_details, "reasons": cov_reasons}

    payload["v016_l4_search_determinism_status"] = det_status
    payload["v016_l4_search_determinism"] = {**det_details, "reasons": det_reasons}

    payload["v016_bc_import_symmetry_status"] = bc_sym_status
    payload["v016_bc_import_symmetry"] = {**bc_sym_details, "reasons": bc_sym_reasons}

    payload["v016_bc_test_coverage_status"] = bc_cov_status
    payload["v016_bc_test_coverage"] = {**bc_cov_details, "reasons": bc_cov_reasons}

    payload["v016_l5_trend_status"] = l5_status if l5_trend else "missing"
    if l5_trend:
        payload["v016_l5_trend"] = {**l5_details, "reasons": l5_reasons}

    reasons = [str(x) for x in payload.get("reasons") or [] if isinstance(x, str)]
    for label, status in [
        ("v016_l4_import_symmetry", sym_status),
        ("v016_executor_line_count", lc_status),
        ("v016_l4_search_determinism", det_status),
        ("v016_bc_import_symmetry", bc_sym_status),
    ]:
        if status != "PASS":
            reasons.append(f"{label}_not_pass")
    if cov_status == "NEEDS_REVIEW":
        reasons.append("v016_l4_test_coverage_needs_review")
    elif cov_status == "FAIL":
        reasons.append("v016_l4_test_coverage_fail")
    if bc_cov_status == "NEEDS_REVIEW":
        reasons.append("v016_bc_test_coverage_needs_review")
    elif bc_cov_status == "FAIL":
        reasons.append("v016_bc_test_coverage_fail")
    if l5_trend and l5_status != "PASS":
        reasons.append("v016_l5_trend_authority_not_stable")
    payload["reasons"] = reasons

    status = str(payload.get("status") or "PASS").strip().upper() or "PASS"
    blocking = [sym_status, lc_status, det_status, bc_sym_status]
    if any(s == "FAIL" for s in blocking):
        status = "FAIL"
    if cov_status == "FAIL" or bc_cov_status == "FAIL":
        status = "FAIL"
    if l5_trend and status == "PASS" and l5_status == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"
    payload["status"] = status

    _write_json(out_path, payload)
    print(json.dumps(payload, indent=2))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
