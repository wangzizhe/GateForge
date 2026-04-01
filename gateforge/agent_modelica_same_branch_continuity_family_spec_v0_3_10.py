from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_same_branch_continuity_family_spec_v0_3_10"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_same_branch_continuity_family_spec_v0_3_10"
FAMILY_ID = "same_branch_continuity_after_partial_progress"
MIN_CANDIDATE_READY_CASES = 8
BASELINE_PROTOCOL_VERSION = "v0_3_10_same_branch_continuity_baseline_authority_v1"
BASELINE_LEVER_NAME = "single_branch_resolution_without_true_stall"
BASELINE_REFERENCE_VERSION = "v0.3.9"
SOURCE_BUCKET = "single_branch_resolution_without_true_stall"


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
    family_id = _norm(candidate.get("v0_3_10_family_id") or candidate.get("family_id"))
    if family_id == FAMILY_ID:
        return True, f"family_ok:{family_id}"
    return False, f"family_not_supported:{family_id}"


def check_source_bucket_gate(candidate: dict) -> tuple[bool, str]:
    bucket = _norm(candidate.get("source_primary_bucket"))
    if bucket == SOURCE_BUCKET:
        return True, f"source_bucket_ok:{bucket}"
    return False, f"source_bucket_not_supported:{bucket}"


def check_branch_identity_gate(candidate: dict) -> tuple[bool, str]:
    current_branch = _norm(candidate.get("current_branch"))
    selected_branch = _norm(candidate.get("selected_branch"))
    sequence = candidate.get("detected_branch_sequence")
    sequence = [_norm(item) for item in sequence if _norm(item)] if isinstance(sequence, list) else []
    if not current_branch or not selected_branch:
        return False, "current_or_selected_branch_missing"
    if not sequence:
        return False, "detected_branch_sequence_missing"
    if len(set(sequence)) != 1:
        return False, "branch_sequence_not_single_branch"
    if sequence[0] != selected_branch:
        return False, "selected_branch_not_equal_to_detected_branch"
    return True, "branch_identity_ok"


def check_non_switch_success_gate(candidate: dict) -> tuple[bool, str]:
    if candidate.get("success_without_branch_switch_evidence") is not True:
        return False, "success_without_branch_switch_evidence_not_true"
    if candidate.get("success_after_branch_switch") is True:
        return False, "success_after_branch_switch_must_be_false"
    if candidate.get("branch_switch_event_observed") is True:
        return False, "branch_switch_event_observed_must_be_false"
    return True, "non_switch_success_ok"


def check_measurement_protocol_gate(candidate: dict) -> tuple[bool, str]:
    protocol = candidate.get("baseline_measurement_protocol")
    if not isinstance(protocol, dict):
        return False, "baseline_measurement_protocol_missing"
    if _norm(protocol.get("protocol_version")) != BASELINE_PROTOCOL_VERSION:
        return False, f"protocol_version_mismatch:{_norm(protocol.get('protocol_version'))}"
    if _norm(protocol.get("baseline_lever_name")) != _norm(BASELINE_LEVER_NAME):
        return False, f"baseline_lever_mismatch:{_norm(protocol.get('baseline_lever_name'))}"
    if _norm(protocol.get("baseline_reference_version")) != _norm(BASELINE_REFERENCE_VERSION):
        return False, f"baseline_reference_mismatch:{_norm(protocol.get('baseline_reference_version'))}"
    flags = protocol.get("enabled_policy_flags") if isinstance(protocol.get("enabled_policy_flags"), dict) else {}
    if bool(flags.get("allow_branch_switch_replan_policy")):
        return False, "branch_switch_replan_policy_must_be_disabled"
    if bool(flags.get("allow_same_branch_continuity_policy")):
        return False, "same_branch_continuity_policy_must_be_disabled"
    return True, "measurement_protocol_ok"


def run_candidate_ready_gates(candidate: dict) -> dict:
    gates = []
    reasons = []
    for gate_fn, gate_name in [
        (check_family_gate, "family_gate"),
        (check_source_bucket_gate, "source_bucket_gate"),
        (check_branch_identity_gate, "branch_identity_gate"),
        (check_non_switch_success_gate, "non_switch_success_gate"),
        (check_measurement_protocol_gate, "measurement_protocol_gate"),
    ]:
        passed, reason = gate_fn(candidate)
        gates.append({"gate": gate_name, "passed": passed, "reason": reason})
        if not passed:
            reasons.append(f"{gate_name}:{reason}")
    return {
        "task_id": str(candidate.get("task_id") or ""),
        "passed": all(item["passed"] for item in gates),
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
        "family_id": FAMILY_ID,
        "total_candidate_count": len(results),
        "admitted_count": len(admitted),
        "rejected_count": len(rejected),
        "targets": {
            "min_candidate_ready_cases": MIN_CANDIDATE_READY_CASES,
            "required_source_bucket": SOURCE_BUCKET,
            "required_success_mode": "success_after_same_branch_continuation",
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
    return "\n".join(
        [
            "# v0.3.10 Same-Branch Continuity Family Spec",
            "",
            f"- lane_status: `{summary.get('lane_status')}`",
            f"- family_id: `{summary.get('family_id')}`",
            f"- total_candidate_count: `{summary.get('total_candidate_count')}`",
            f"- admitted_count: `{summary.get('admitted_count')}`",
            f"- rejected_count: `{summary.get('rejected_count')}`",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate candidate-ready status for the v0.3.10 same-branch continuity family.")
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
