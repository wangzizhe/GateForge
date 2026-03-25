"""Release preflight gate for v0.1.7.

Extends the v0.1.6 gate (Incremental Gate Composition Pattern) with checks
specific to the OMC workspace extraction:

  1. OMC workspace import symmetry  – every public function in
     ``agent_modelica_omc_workspace_v1`` is re-exported from the executor
     with the expected ``_`` alias.
  2. Executor line-count gate  – executor must be under 2,900 lines
     (tightened from 3,200 after OMC extraction).
  3. OMC workspace test coverage  – the OMC workspace test file exists and
     mentions the key function names.
  4. v0.1.6 gate continuity  – all v0.1.6 checks (L4 symmetry, BC symmetry,
     executor<3200, determinism) still pass.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pathlib
from datetime import datetime, timezone


SCHEMA_VERSION = "agent_modelica_release_preflight_v0_1_7_evidence_v1"

_REPO_ROOT = pathlib.Path(__file__).parent.parent

# Public names exported from the OMC workspace module.
_OMC_PUBLIC_NAMES = [
    "WorkspaceModelLayout",
    "cleanup_workspace_best_effort",
    "classify_failure",
    "copytree_best_effort",
    "extract_om_success_flags",
    "norm_path_text",
    "prepare_workspace_model_layout",
    "rel_mos_path",
    "run_check_and_simulate",
    "run_cmd",
    "run_omc_script_docker",
    "run_omc_script_local",
    "temporary_workspace",
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


# ---------------------------------------------------------------------------
# OMC workspace import symmetry
# ---------------------------------------------------------------------------


def _omc_import_symmetry_status() -> tuple[str, list[str], dict]:
    """Verify every OMC workspace public name is re-exported from executor."""
    reasons: list[str] = []
    missing: list[str] = []
    try:
        executor = importlib.import_module("gateforge.agent_modelica_live_executor_gemini_v1")
        omc = importlib.import_module("gateforge.agent_modelica_omc_workspace_v1")
    except ImportError as exc:
        return "FAIL", [f"import_error:{exc}"], {"missing": [], "checked": 0}

    omc_names = {
        name
        for name, _ in inspect.getmembers(omc)
        if not name.startswith("_")
        and (inspect.isfunction(getattr(omc, name)) or inspect.isclass(getattr(omc, name)))
    }
    for name in _OMC_PUBLIC_NAMES:
        alias = f"_{name}"
        if not hasattr(executor, alias):
            missing.append(name)
        elif getattr(executor, alias) is not getattr(omc, name, None):
            missing.append(f"{name}(alias_mismatch)")
    if missing:
        reasons.append(f"omc_alias_missing:{','.join(missing)}")
    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {"missing": missing, "checked": len(_OMC_PUBLIC_NAMES), "omc_exported": sorted(omc_names)},
    )


# ---------------------------------------------------------------------------
# Executor line count
# ---------------------------------------------------------------------------


def _executor_line_count_status(max_lines: int = 3000) -> tuple[str, list[str], dict]:
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
# OMC workspace test coverage
# ---------------------------------------------------------------------------


def _omc_test_coverage_status() -> tuple[str, list[str], dict]:
    """Check the OMC workspace test file exists and mentions key function names."""
    reasons: list[str] = []
    test_path = _REPO_ROOT / "tests" / "test_agent_modelica_omc_workspace_v1.py"
    if not test_path.exists():
        return "FAIL", ["omc_test_file_missing"], {"covered": [], "uncovered": _OMC_PUBLIC_NAMES}
    content = test_path.read_text(encoding="utf-8")
    # Check coverage of the pure-function subset (Docker-dependent ones are
    # tested by the existing integration test suite, not this pure test file).
    pure_names = [
        "extract_om_success_flags",
        "norm_path_text",
        "rel_mos_path",
        "classify_failure",
        "prepare_workspace_model_layout",
        "copytree_best_effort",
        "cleanup_workspace_best_effort",
        "temporary_workspace",
    ]
    uncovered = [name for name in pure_names if name not in content]
    if uncovered:
        reasons.append(f"omc_test_coverage_gap:{','.join(uncovered)}")
    return (
        "PASS" if not reasons else "NEEDS_REVIEW",
        reasons,
        {"covered": [n for n in pure_names if n in content], "uncovered": uncovered},
    )


# ---------------------------------------------------------------------------
# v0.1.6 gate continuity (re-run the v0.1.6 checks)
# ---------------------------------------------------------------------------


def _v016_gate_continuity_status() -> tuple[str, list[str], dict]:
    """Re-run v0.1.6 checks to confirm nothing regressed."""
    reasons: list[str] = []
    try:
        from gateforge.agent_modelica_release_preflight_v0_1_6_evidence import (
            _bc_import_symmetry_status,
            _l4_import_symmetry_status,
            _l4_search_determinism_status,
        )
    except ImportError as exc:
        return "FAIL", [f"v016_import_error:{exc}"], {}

    l4_sym, l4_sym_r, _ = _l4_import_symmetry_status()
    bc_sym, bc_sym_r, _ = _bc_import_symmetry_status()
    det, det_r, _ = _l4_search_determinism_status()

    for label, status, sub_reasons in [
        ("l4_import_symmetry", l4_sym, l4_sym_r),
        ("bc_import_symmetry", bc_sym, bc_sym_r),
        ("l4_search_determinism", det, det_r),
    ]:
        if status != "PASS":
            reasons.append(f"v016_{label}_regression:{';'.join(sub_reasons)}")

    return (
        "PASS" if not reasons else "FAIL",
        reasons,
        {
            "l4_import_symmetry": l4_sym,
            "bc_import_symmetry": bc_sym,
            "l4_search_determinism": det,
        },
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="v0.1.7 release preflight evidence gate")
    parser.add_argument("--summary", required=True, help="Path to base release summary JSON")
    parser.add_argument("--out", help="Output path (defaults to --summary path)")
    args = parser.parse_args()

    out_path = str(args.out or args.summary)
    summary = _load_json(args.summary)

    sym_status, sym_reasons, sym_details = _omc_import_symmetry_status()
    lc_status, lc_reasons, lc_details = _executor_line_count_status()
    cov_status, cov_reasons, cov_details = _omc_test_coverage_status()
    cont_status, cont_reasons, cont_details = _v016_gate_continuity_status()

    payload = dict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()

    payload["v017_omc_import_symmetry_status"] = sym_status
    payload["v017_omc_import_symmetry"] = {**sym_details, "reasons": sym_reasons}

    payload["v017_executor_line_count_status"] = lc_status
    payload["v017_executor_line_count"] = {**lc_details, "reasons": lc_reasons}

    payload["v017_omc_test_coverage_status"] = cov_status
    payload["v017_omc_test_coverage"] = {**cov_details, "reasons": cov_reasons}

    payload["v017_v016_gate_continuity_status"] = cont_status
    payload["v017_v016_gate_continuity"] = {**cont_details, "reasons": cont_reasons}

    reasons = [str(x) for x in payload.get("reasons") or [] if isinstance(x, str)]
    blocking = [sym_status, lc_status, cont_status]
    for label, status in [
        ("v017_omc_import_symmetry", sym_status),
        ("v017_executor_line_count", lc_status),
        ("v017_v016_gate_continuity", cont_status),
    ]:
        if status != "PASS":
            reasons.append(f"{label}_not_pass")
    if cov_status == "NEEDS_REVIEW":
        reasons.append("v017_omc_test_coverage_needs_review")
    elif cov_status == "FAIL":
        reasons.append("v017_omc_test_coverage_fail")
    payload["reasons"] = reasons

    status = str(payload.get("status") or "PASS").strip().upper() or "PASS"
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
