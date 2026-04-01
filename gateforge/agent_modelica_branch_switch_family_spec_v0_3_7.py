from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_branch_switch_family_spec_v0_3_7"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_branch_switch_family_spec_v0_3_7"
FAMILY_ID = "post_restore_branch_switch_after_stall"
MIN_CANDIDATE_READY_CASES = 8
BASELINE_PROTOCOL_VERSION = "v0_3_7_branch_switch_baseline_authority_v1"
BASELINE_LEVER_NAME = "simulate_error_parameter_recovery_sweep"
BASELINE_REFERENCE_VERSION = "v0.3.6"


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
    family_id = _norm(candidate.get("v0_3_7_family_id") or candidate.get("family_id"))
    if family_id == FAMILY_ID:
        return True, f"family_ok:{family_id}"
    return False, f"family_not_supported:{family_id}"


def check_entry_state_gate(candidate: dict) -> tuple[bool, str]:
    entry_bucket = _norm(candidate.get("required_entry_bucket"))
    if entry_bucket == "stalled_search_after_progress":
        return True, "required_entry_bucket_ok:stalled_search_after_progress"
    return False, f"required_entry_bucket_not_supported:{entry_bucket}"


def check_branch_candidates_gate(candidate: dict) -> tuple[bool, str]:
    branches = candidate.get("candidate_branches")
    if not isinstance(branches, list) or len(branches) < 2:
        return False, "candidate_branches_missing_or_too_small"
    current_branch = _norm(candidate.get("current_branch"))
    preferred_branch = _norm(candidate.get("preferred_branch"))
    seen = set()
    for row in branches:
        if not isinstance(row, dict):
            return False, "candidate_branch_not_object"
        branch_id = _norm(row.get("branch_id"))
        branch_kind = _norm(row.get("branch_kind"))
        trigger_signal = _norm(row.get("trigger_signal"))
        if not branch_id or not branch_kind:
            return False, "candidate_branch_missing_required_fields"
        if trigger_signal != "stalled_search_after_progress":
            return False, f"candidate_branch_trigger_mismatch:{trigger_signal}"
        seen.add(branch_id)
    if preferred_branch and preferred_branch not in seen:
        return False, f"preferred_branch_not_in_candidates:{preferred_branch}"
    if current_branch and current_branch not in seen:
        return False, f"current_branch_not_in_candidates:{current_branch}"
    if preferred_branch and current_branch and preferred_branch == current_branch:
        return False, "preferred_branch_must_differ_from_current_branch"
    return True, "branch_candidates_ok"


def check_measurement_protocol_gate(candidate: dict) -> tuple[bool, str]:
    protocol = candidate.get("baseline_measurement_protocol")
    if not isinstance(protocol, dict):
        return False, "baseline_measurement_protocol_missing"
    if _norm(protocol.get("protocol_version")) != BASELINE_PROTOCOL_VERSION:
        return False, f"protocol_version_mismatch:{_norm(protocol.get('protocol_version'))}"
    if _norm(protocol.get("baseline_lever_name")) != BASELINE_LEVER_NAME:
        return False, f"baseline_lever_mismatch:{_norm(protocol.get('baseline_lever_name'))}"
    if _norm(protocol.get("baseline_reference_version")) != _norm(BASELINE_REFERENCE_VERSION):
        return False, f"baseline_reference_mismatch:{_norm(protocol.get('baseline_reference_version'))}"
    flags = protocol.get("enabled_policy_flags") if isinstance(protocol.get("enabled_policy_flags"), dict) else {}
    if bool(flags.get("allow_branch_switch_replan_policy")):
        return False, "branch_switch_policy_must_be_disabled_in_baseline"
    if flags.get("allow_baseline_single_sweep") is not True:
        return False, "baseline_single_sweep_not_enabled"
    return True, "measurement_protocol_ok:v0_3_6_branch_switch_baseline"


def run_candidate_ready_gates(candidate: dict) -> dict:
    gates = []
    reasons = []
    for gate_fn, gate_name in [
        (check_family_gate, "family_gate"),
        (check_entry_state_gate, "entry_state_gate"),
        (check_branch_candidates_gate, "branch_candidates_gate"),
        (check_measurement_protocol_gate, "measurement_protocol_gate"),
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
    results = [run_candidate_ready_gates(row) for row in candidates]
    admitted = [row for row in results if row["passed"]]
    rejected = [row for row in results if not row["passed"]]
    rejection_summary: dict[str, int] = {}
    for row in rejected:
        for reason in row.get("reasons") or []:
            rejection_summary[str(reason)] = int(rejection_summary.get(str(reason)) or 0) + 1

    lane_status = "EMPTY"
    if results:
        lane_status = "CANDIDATE_READY" if len(admitted) >= MIN_CANDIDATE_READY_CASES else "NEEDS_MORE_GENERATION"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lane_status": lane_status,
        "total_candidate_count": len(results),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "targets": {
            "min_candidate_ready_cases": MIN_CANDIDATE_READY_CASES,
            "required_entry_bucket": "stalled_search_after_progress",
        },
        "admitted_task_ids": [str(row.get("task_id") or "") for row in admitted],
        "rejected_task_ids": [str(row.get("task_id") or "") for row in rejected],
        "rejection_summary": rejection_summary,
        "gate_results": results,
    }


def build_lane_summary_from_taskset(*, candidate_taskset_path: str, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    payload = _load_json(candidate_taskset_path)
    rows = payload.get("tasks")
    candidates = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    summary = build_lane_summary(candidates)
    summary["candidate_taskset_path"] = (
        str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path)
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def render_markdown(summary: dict) -> str:
    lines = [
        "# v0.3.7 Branch-Switch Family Spec",
        "",
        f"- lane_status: `{summary.get('lane_status')}`",
        f"- total_candidate_count: `{summary.get('total_candidate_count')}`",
        f"- admitted_count: `{summary.get('admitted_count')}`",
        f"- rejected_count: `{summary.get('rejected_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate candidate-ready status for the v0.3.7 branch-switch-after-stall family.")
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
