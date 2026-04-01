"""
Post-restore harder lane family spec for v0.3.5.

Block 0 root-cause analysis established three mechanisms that make families land
in deterministic coverage:
  1. Stage-too-early manifestation (error caught at stage_1/2/3, not stage_4/5)
  2. Source restore bypass (executor has a source-restore path for the failure type)
  3. Marker transparency (gateforge_ markers allow deterministic rule removal)

This module defines the v0.3.5 family spec for post-restore harder lanes that
explicitly avoid all three mechanisms.

Two family directions are supported:
  - post_restore_residual_conflict: dual-layer mutation (hidden base + marked top)
  - branch_sensitive_multi_round_trap: branch-selection required after initial progress

Design constraints enforced by admission gate functions in this module.

Schema: agent_modelica_post_restore_family_spec_v0_3_5
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_post_restore_family_spec_v0_3_5"

# Families defined in this spec
FAMILY_IDS = {
    "post_restore_residual_conflict",
    "branch_sensitive_multi_round_trap",
}

# Stage subtypes that disqualify a candidate (error caught too early)
DISQUALIFIED_STAGE_SUBTYPES = {
    "stage_1_parse_syntax",
    "stage_2_structural_balance_reference",
    "stage_3_type_connector_consistency",
    "stage_3_behavioral_contract_semantic",
}

# Stage subtypes required for Layer 4 candidacy
REQUIRED_STAGE_SUBTYPES = {
    "stage_4_initialization_singularity",
    "stage_5_runtime_numerical_instability",
}

# Failure types that have executor source restore paths (disqualify Direction A single-layer)
EXECUTOR_SOURCE_RESTORE_COVERED_TYPES = {
    "coupled_conflict_failure",
    "cascading_structural_failure",
    "false_friend_patch_trap",
    "parameter_binding_error",
    "overconstrained_system",
    "underconstrained_system",
    "solver_sensitive_simulate_failure",
    "event_logic_error",
    "semantic_drift_after_compile_pass",
    "cross_component_parameter_coupling_error",
    "control_loop_sign_semantic_drift",
    "mode_switch_guard_logic_error",
    "steady_state_target_violation",
    "transient_response_contract_violation",
    "mode_transition_contract_violation",
    "param_perturbation_robustness_violation",
    "initial_condition_robustness_violation",
    "scenario_switch_robustness_violation",
}

# Minimum target for candidate-ready lane (Block A minimum)
MIN_CANDIDATE_READY_COUNT = 10

# Preferred target for freeze-ready lane (Block A preferred)
MIN_FREEZE_READY_COUNT = 10


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def check_stage_gate(candidate: dict) -> tuple[bool, str]:
    """
    Gate 1: error must manifest only at stage_4 or stage_5.

    Returns (passed, reason).
    """
    dominant = _norm(candidate.get("dominant_stage_subtype") or candidate.get("stage_subtype") or "")
    if dominant in {s.lower() for s in DISQUALIFIED_STAGE_SUBTYPES}:
        return False, f"stage_disqualified:{dominant}"
    if dominant in {s.lower() for s in REQUIRED_STAGE_SUBTYPES}:
        return True, f"stage_ok:{dominant}"
    # Unknown stage — treat as provisional pass with warning
    return True, f"stage_unknown_provisional:{dominant}"


def check_source_restore_gate(candidate: dict) -> tuple[bool, str]:
    """
    Gate 2: single-layer source restore must not fully resolve the mutation.

    For Direction A (dual-layer mutation): pass if dual_layer_mutation=true is set.
    For Direction B (behavioral contract): pass if behavioral_contract_mode=true is set.
    For other cases: fail if declared_failure_type is in executor source restore dispatch
    AND neither dual_layer nor behavioral_contract mode is declared.

    Returns (passed, reason).
    """
    declared = _norm(candidate.get("declared_failure_type") or candidate.get("failure_type") or "")
    dual_layer = bool(candidate.get("dual_layer_mutation"))
    behavioral_contract = bool(candidate.get("behavioral_contract_mode"))

    if dual_layer:
        return True, "source_restore_gate_ok:dual_layer_mutation"
    if behavioral_contract:
        return True, "source_restore_gate_ok:behavioral_contract_mode"
    if declared in {t.lower() for t in EXECUTOR_SOURCE_RESTORE_COVERED_TYPES}:
        return False, f"source_restore_bypass_risk:{declared}"
    return True, f"source_restore_gate_ok:failure_type_not_in_dispatch:{declared}"


def check_marker_gate(candidate: dict) -> tuple[bool, str]:
    """
    Gate 3: single marker removal must not fully resolve the mutation.

    Passes if:
    - dual_layer_mutation=true (top layer uses markers, but base layer has no markers)
    - behavioral_contract_mode=true (no marker-based repair path)
    - marker_only_repair=false is explicitly declared
    - or no marker_only_repair information is present (provisional pass)

    Fails if marker_only_repair=true is explicitly declared.

    Returns (passed, reason).
    """
    dual_layer = bool(candidate.get("dual_layer_mutation"))
    behavioral_contract = bool(candidate.get("behavioral_contract_mode"))
    marker_only = candidate.get("marker_only_repair")

    if dual_layer:
        return True, "marker_gate_ok:dual_layer_base_has_no_marker"
    if behavioral_contract:
        return True, "marker_gate_ok:behavioral_contract_no_marker_path"
    if marker_only is True:
        return False, "marker_only_repair_disqualifies_candidate"
    if marker_only is False:
        return True, "marker_gate_ok:marker_only_repair_explicitly_false"
    return True, "marker_gate_provisional:marker_only_repair_not_declared"


def check_planner_sensitivity_gate(candidate: dict) -> tuple[bool, str]:
    """
    Gate 4: candidate must have at least one planner-sensitivity signal.

    Accepts any of:
    - dual_layer_mutation = True (structural guarantee: Round 1 removes marked top,
      Round 2 source_repair is a no-op because current_text == source_model_text,
      so LLM must be invoked; no empirical GateForge run required at screening time)
    - planner_invoked = true (empirical evidence from GateForge run)
    - rounds_used > 1 and llm_request_count > 0 (empirical evidence)
    - resolution_path = llm_planner_assisted or rule_then_llm (empirical evidence)

    Returns (passed, reason).
    """
    # Structural bypass (pre-GateForge screening): dual-layer mutation design
    # guarantees LLM invocation in Round 2 by construction (source_repair is
    # a no-op because current_text == source_model_text after Round 1 removes
    # the marked top). Only applies when NO empirical GateForge evidence is
    # present yet; if evidence is present, use it below (post-GateForge path).
    has_empirical_evidence = (
        candidate.get("planner_invoked") is not None
        or candidate.get("rounds_used") is not None
        or candidate.get("resolution_path") is not None
    )
    if candidate.get("dual_layer_mutation") is True and not has_empirical_evidence:
        return True, "planner_sensitivity_ok:dual_layer_structural_guarantee"

    planner_invoked = bool(candidate.get("planner_invoked"))
    rounds_used = int(candidate.get("rounds_used") or 0)
    llm_count = int(candidate.get("llm_request_count") or 0)
    resolution_path = _norm(candidate.get("resolution_path") or "")

    if planner_invoked:
        return True, "planner_sensitivity_ok:planner_invoked"
    if rounds_used > 1 and llm_count > 0:
        return True, "planner_sensitivity_ok:multi_round_with_llm"
    if resolution_path in {"llm_planner_assisted", "rule_then_llm"}:
        return True, f"planner_sensitivity_ok:resolution_path:{resolution_path}"
    return False, "planner_sensitivity_not_met"


def run_admission_gates(candidate: dict) -> dict:
    """
    Run all four admission gates for a candidate case.

    Returns a gate result dict with:
    - passed: bool (all four gates passed)
    - gates: list of individual gate results
    - reasons: list of failure reasons
    """
    gates = []
    reasons = []

    for gate_fn, gate_name in [
        (check_stage_gate, "stage_gate"),
        (check_source_restore_gate, "source_restore_gate"),
        (check_marker_gate, "marker_gate"),
        (check_planner_sensitivity_gate, "planner_sensitivity_gate"),
    ]:
        passed, reason = gate_fn(candidate)
        gates.append({"gate": gate_name, "passed": passed, "reason": reason})
        if not passed:
            reasons.append(f"{gate_name}:{reason}")

    all_passed = all(g["passed"] for g in gates)
    return {
        "task_id": str(candidate.get("task_id") or ""),
        "passed": all_passed,
        "gates": gates,
        "reasons": reasons,
    }


def build_lane_summary(candidates: list[dict]) -> dict:
    """
    Evaluate a list of candidate cases and build a lane summary.

    Returns a summary dict with admission status and composition metrics.
    """
    results = [run_admission_gates(c) for c in candidates]
    admitted = [r for r in results if r["passed"]]
    rejected = [r for r in results if not r["passed"]]

    admitted_count = len(admitted)
    total_count = len(results)

    # Composition metrics (only for admitted candidates)
    admitted_ids = {r["task_id"] for r in admitted}
    admitted_candidates = [c for c in candidates if str(c.get("task_id") or "") in admitted_ids]

    planner_invoked_count = sum(1 for c in admitted_candidates if bool(c.get("planner_invoked")))
    deterministic_only_count = sum(
        1 for c in admitted_candidates
        if _norm(c.get("resolution_path") or "") == "deterministic_rule_only"
    )

    planner_invoked_pct = round(100.0 * planner_invoked_count / admitted_count, 1) if admitted_count else 0.0
    deterministic_only_pct = round(100.0 * deterministic_only_count / admitted_count, 1) if admitted_count else 0.0

    composition_ok = deterministic_only_pct <= 40.0
    size_candidate_ready = admitted_count >= MIN_CANDIDATE_READY_COUNT
    size_freeze_ready = admitted_count >= MIN_FREEZE_READY_COUNT

    lane_status = "DISQUALIFIED"
    if admitted_count == 0:
        lane_status = "EMPTY"
    elif not composition_ok:
        lane_status = "COMPOSITION_FAIL"
    elif size_freeze_ready:
        lane_status = "FREEZE_READY"
    elif size_candidate_ready:
        lane_status = "CANDIDATE_READY"
    else:
        lane_status = "BELOW_MINIMUM"

    rejection_summary: dict[str, int] = {}
    for r in rejected:
        for reason in r["reasons"]:
            rejection_summary[reason] = rejection_summary.get(reason, 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lane_status": lane_status,
        "total_candidate_count": total_count,
        "admitted_count": admitted_count,
        "rejected_count": len(rejected),
        "composition": {
            "planner_invoked_count": planner_invoked_count,
            "planner_invoked_pct": planner_invoked_pct,
            "deterministic_only_count": deterministic_only_count,
            "deterministic_only_pct": deterministic_only_pct,
            "composition_ok": composition_ok,
        },
        "targets": {
            "min_candidate_ready": MIN_CANDIDATE_READY_COUNT,
            "min_freeze_ready": MIN_FREEZE_READY_COUNT,
            "size_candidate_ready": size_candidate_ready,
            "size_freeze_ready": size_freeze_ready,
        },
        "admitted_task_ids": [r["task_id"] for r in admitted],
        "rejected_task_ids": [r["task_id"] for r in rejected],
        "rejection_summary": rejection_summary,
        "gate_results": results,
    }


def render_markdown(summary: dict) -> str:
    lines = [
        "# Post-Restore Family Spec v0.3.5 — Lane Summary",
        "",
        f"- lane_status: `{summary.get('lane_status')}`",
        f"- admitted_count: `{summary.get('admitted_count')}`",
        f"- rejected_count: `{summary.get('rejected_count')}`",
        "",
        "## Composition",
        "",
    ]
    comp = summary.get("composition") or {}
    lines.append(f"- planner_invoked_pct: `{comp.get('planner_invoked_pct')}%`")
    lines.append(f"- deterministic_only_pct: `{comp.get('deterministic_only_pct')}%`")
    lines.append(f"- composition_ok: `{comp.get('composition_ok')}`")
    lines.append("")
    lines.append("## Targets")
    lines.append("")
    targets = summary.get("targets") or {}
    lines.append(f"- min_candidate_ready: `{targets.get('min_candidate_ready')}`")
    lines.append(f"- min_freeze_ready: `{targets.get('min_freeze_ready')}`")
    lines.append(f"- size_candidate_ready: `{targets.get('size_candidate_ready')}`")
    lines.append(f"- size_freeze_ready: `{targets.get('size_freeze_ready')}`")
    lines.append("")
    rejection_summary = summary.get("rejection_summary") or {}
    if rejection_summary:
        lines.append("## Rejection Summary")
        lines.append("")
        for reason, count in sorted(rejection_summary.items(), key=lambda x: -x[1]):
            lines.append(f"- `{reason}`: {count} case(s)")
        lines.append("")
    return "\n".join(lines)


def run_lane_summary(
    *,
    candidates_path: str,
    out_dir: str,
) -> dict:
    p = Path(candidates_path)
    raw = _load_json(p)
    candidates_list: list[dict] = []
    if isinstance(raw.get("tasks"), list):
        candidates_list = [r for r in raw["tasks"] if isinstance(r, dict)]
    elif isinstance(raw.get("cases"), list):
        candidates_list = [r for r in raw["cases"] if isinstance(r, dict)]
    elif isinstance(raw, list):
        candidates_list = [r for r in raw if isinstance(r, dict)]

    summary = build_lane_summary(candidates_list)
    out_root = Path(out_dir)
    _write_json(out_root / "post_restore_lane_summary.json", summary)
    _write_text(out_root / "post_restore_lane_summary.md", render_markdown(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate post-restore harder lane candidates for v0.3.5 Block A."
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to JSON file with candidate cases (tasks/cases array or list).",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts/agent_modelica_post_restore_family_spec_v0_3_5",
        help="Output directory for summary JSON and Markdown.",
    )
    args = parser.parse_args()
    summary = run_lane_summary(
        candidates_path=str(args.candidates),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "lane_status": summary.get("lane_status"),
                "admitted_count": summary.get("admitted_count"),
                "rejected_count": summary.get("rejected_count"),
            },
            indent=2,
        )
    )
    return 0 if summary.get("lane_status") in {"CANDIDATE_READY", "FREEZE_READY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
