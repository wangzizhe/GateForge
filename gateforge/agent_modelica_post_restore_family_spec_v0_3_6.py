from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_post_restore_family_spec_v0_3_5 import (
    check_marker_gate,
    check_planner_sensitivity_gate,
    check_source_restore_gate,
    check_stage_gate,
)


SCHEMA_VERSION = "agent_modelica_post_restore_family_spec_v0_3_6"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_post_restore_family_spec_v0_3_6"
MIN_FREEZE_READY_CASES = 10
MAX_SINGLE_SWEEP_SUCCESS_RATE_PCT = 40.0
MAX_DETERMINISTIC_ONLY_PCT = 30.0
MIN_FIRST_CORRECTION_RESIDUAL_CASES = 3
MIN_RESIDUAL_BUCKET_CASES = 3
BASELINE_PROTOCOL_VERSION = "v0_3_6_single_sweep_baseline_authority_v1"
BASELINE_LEVER_NAME = "simulate_error_parameter_recovery_sweep"
BASELINE_REFERENCE_VERSION = "v0.3.5"
FAMILY_IDS = {
    "post_restore_residual_semantic_conflict",
    "post_restore_branch_followup_trap",
}
QUALIFYING_FAILURE_BUCKETS = {
    "residual_semantic_conflict_after_restore",
    "wrong_branch_after_restore",
    "stalled_search_after_progress",
}


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


def check_family_gate(candidate: dict) -> tuple[bool, str]:
    family_id = _norm(candidate.get("v0_3_6_family_id") or candidate.get("family_id") or "")
    if family_id in {x.lower() for x in FAMILY_IDS}:
        return True, f"family_ok:{family_id}"
    return False, f"family_not_supported:{family_id}"


def check_measurement_protocol_gate(candidate: dict) -> tuple[bool, str]:
    protocol = candidate.get("baseline_measurement_protocol")
    if not isinstance(protocol, dict):
        return False, "baseline_measurement_protocol_missing"

    protocol_version = _norm(protocol.get("protocol_version"))
    lever_name = _norm(protocol.get("baseline_lever_name"))
    reference_version = _norm(protocol.get("baseline_reference_version"))
    enabled_flags = protocol.get("enabled_policy_flags") if isinstance(protocol.get("enabled_policy_flags"), dict) else {}

    if protocol_version != BASELINE_PROTOCOL_VERSION.lower():
        return False, f"protocol_version_mismatch:{protocol_version}"
    if lever_name != BASELINE_LEVER_NAME.lower():
        return False, f"baseline_lever_mismatch:{lever_name}"
    if reference_version != BASELINE_REFERENCE_VERSION.lower():
        return False, f"baseline_reference_mismatch:{reference_version}"
    if enabled_flags.get("allow_baseline_single_sweep") is not True:
        return False, "baseline_single_sweep_not_enabled"
    if enabled_flags.get("allow_new_multistep_policy") is not False:
        return False, "new_multistep_policy_must_be_disabled"
    return True, "measurement_protocol_ok:v0_3_5_single_sweep_authority"


def _single_sweep_outcome(candidate: dict) -> str:
    direct = _norm(candidate.get("single_sweep_outcome"))
    if direct:
        return direct
    if candidate.get("single_sweep_resolved") is True:
        return "resolved"
    if candidate.get("first_correction_success") is True and candidate.get("residual_failure_after_first_correction") is True:
        return "residual_failure_after_first_correction"
    if _norm(candidate.get("post_restore_failure_bucket")) in QUALIFYING_FAILURE_BUCKETS:
        return "residual_failure_after_first_correction"
    return ""


def check_residual_harder_gate(candidate: dict) -> tuple[bool, str]:
    outcome = _single_sweep_outcome(candidate)
    bucket = _norm(candidate.get("post_restore_failure_bucket"))
    if outcome == "resolved":
        return False, "single_sweep_resolved_too_easy"
    if outcome == "residual_failure_after_first_correction":
        return True, "residual_harder_ok:residual_failure_after_first_correction"
    if bucket in QUALIFYING_FAILURE_BUCKETS:
        return True, f"residual_harder_ok:failure_bucket:{bucket}"
    return False, "residual_harder_not_met"


def run_admission_gates(candidate: dict) -> dict:
    gates = []
    reasons = []
    for gate_fn, gate_name in [
        (check_family_gate, "family_gate"),
        (check_stage_gate, "stage_gate"),
        (check_source_restore_gate, "source_restore_gate"),
        (check_marker_gate, "marker_gate"),
        (check_planner_sensitivity_gate, "planner_sensitivity_gate"),
        (check_measurement_protocol_gate, "measurement_protocol_gate"),
        (check_residual_harder_gate, "residual_harder_gate"),
    ]:
        passed, reason = gate_fn(candidate)
        gates.append({"gate": gate_name, "passed": passed, "reason": reason})
        if not passed:
            reasons.append(f"{gate_name}:{reason}")
    return {
        "task_id": str(candidate.get("task_id") or ""),
        "passed": all(g["passed"] for g in gates),
        "gates": gates,
        "reasons": reasons,
    }


def build_lane_summary(candidates: list[dict]) -> dict:
    results = [run_admission_gates(c) for c in candidates]
    admitted = [r for r in results if r["passed"]]
    rejected = [r for r in results if not r["passed"]]

    admitted_ids = {str(r.get("task_id") or "") for r in admitted}
    admitted_candidates = [c for c in candidates if str(c.get("task_id") or "") in admitted_ids]
    evaluable_candidates = [
        c
        for c in candidates
        if check_family_gate(c)[0]
        and check_stage_gate(c)[0]
        and check_source_restore_gate(c)[0]
        and check_marker_gate(c)[0]
        and check_planner_sensitivity_gate(c)[0]
        and check_measurement_protocol_gate(c)[0]
    ]

    total = len(results)
    admitted_count = len(admitted)
    deterministic_only_count = sum(
        1 for c in evaluable_candidates if _norm(c.get("resolution_path")) == "deterministic_rule_only"
    )
    single_sweep_success_count = sum(
        1 for c in evaluable_candidates if _single_sweep_outcome(c) == "resolved"
    )
    first_correction_residual_count = sum(
        1 for c in evaluable_candidates if _single_sweep_outcome(c) == "residual_failure_after_first_correction"
    )
    residual_bucket_count = sum(
        1 for c in evaluable_candidates if _norm(c.get("post_restore_failure_bucket")) in QUALIFYING_FAILURE_BUCKETS
    )
    evaluable_count = len(evaluable_candidates)
    deterministic_only_pct = round(100.0 * deterministic_only_count / evaluable_count, 1) if evaluable_count else 0.0
    single_sweep_success_rate_pct = round(100.0 * single_sweep_success_count / evaluable_count, 1) if evaluable_count else 0.0

    composition_ok = deterministic_only_pct <= MAX_DETERMINISTIC_ONLY_PCT
    harder_than_single_sweep = single_sweep_success_rate_pct <= MAX_SINGLE_SWEEP_SUCCESS_RATE_PCT
    residual_progress_ok = first_correction_residual_count >= MIN_FIRST_CORRECTION_RESIDUAL_CASES
    residual_bucket_ok = residual_bucket_count >= MIN_RESIDUAL_BUCKET_CASES
    freeze_ready = (
        admitted_count >= MIN_FREEZE_READY_CASES
        and composition_ok
        and harder_than_single_sweep
        and residual_progress_ok
        and residual_bucket_ok
    )
    lane_status = "FREEZE_READY" if freeze_ready else "NEEDS_MORE_GENERATION"
    if admitted_count and not freeze_ready:
        lane_status = "ADMISSION_VALID"
    if not total:
        lane_status = "EMPTY"

    rejection_summary: dict[str, int] = {}
    for row in rejected:
        for reason in row.get("reasons") or []:
            rejection_summary[str(reason)] = int(rejection_summary.get(str(reason)) or 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lane_status": lane_status,
        "total_candidate_count": total,
        "admitted_count": admitted_count,
        "rejected_count": len(rejected),
        "evaluable_count": evaluable_count,
        "targets": {
            "min_freeze_ready_cases": MIN_FREEZE_READY_CASES,
            "max_single_sweep_success_rate_pct": MAX_SINGLE_SWEEP_SUCCESS_RATE_PCT,
            "max_deterministic_only_pct": MAX_DETERMINISTIC_ONLY_PCT,
            "min_first_correction_residual_cases": MIN_FIRST_CORRECTION_RESIDUAL_CASES,
            "min_residual_bucket_cases": MIN_RESIDUAL_BUCKET_CASES,
        },
        "composition": {
            "deterministic_only_count": deterministic_only_count,
            "deterministic_only_pct": deterministic_only_pct,
            "single_sweep_success_count": single_sweep_success_count,
            "single_sweep_success_rate_pct": single_sweep_success_rate_pct,
            "first_correction_residual_count": first_correction_residual_count,
            "residual_bucket_count": residual_bucket_count,
        },
        "threshold_checks": {
            "composition_ok": composition_ok,
            "harder_than_single_sweep": harder_than_single_sweep,
            "residual_progress_ok": residual_progress_ok,
            "residual_bucket_ok": residual_bucket_ok,
        },
        "admitted_task_ids": [str(r.get("task_id") or "") for r in admitted],
        "rejected_task_ids": [str(r.get("task_id") or "") for r in rejected],
        "rejection_summary": rejection_summary,
        "gate_results": results,
    }


def build_lane_summary_from_taskset(
    *,
    candidate_taskset_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(candidate_taskset_path)
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    candidates = [row for row in rows if isinstance(row, dict)]
    summary = build_lane_summary(candidates)
    summary["candidate_taskset_path"] = (
        str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path)
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def render_markdown(summary: dict) -> str:
    comp = summary.get("composition") or {}
    checks = summary.get("threshold_checks") or {}
    lines = [
        "# Post-Restore Family Spec v0.3.6 — Lane Summary",
        "",
        f"- lane_status: `{summary.get('lane_status')}`",
        f"- admitted_count: `{summary.get('admitted_count')}`",
        f"- total_candidate_count: `{summary.get('total_candidate_count')}`",
        "",
        "## Threshold Checks",
        "",
        f"- single_sweep_success_rate_pct: `{comp.get('single_sweep_success_rate_pct')}%`",
        f"- deterministic_only_pct: `{comp.get('deterministic_only_pct')}%`",
        f"- first_correction_residual_count: `{comp.get('first_correction_residual_count')}`",
        f"- residual_bucket_count: `{comp.get('residual_bucket_count')}`",
        f"- harder_than_single_sweep: `{checks.get('harder_than_single_sweep')}`",
        f"- composition_ok: `{checks.get('composition_ok')}`",
        f"- residual_progress_ok: `{checks.get('residual_progress_ok')}`",
        f"- residual_bucket_ok: `{checks.get('residual_bucket_ok')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate v0.3.6 post-restore harder-lane admission gates.")
    parser.add_argument("--candidate-taskset", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_lane_summary_from_taskset(
        candidate_taskset_path=str(args.candidate_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"lane_status": payload.get("lane_status"), "admitted_count": payload.get("admitted_count")}))


if __name__ == "__main__":
    main()
