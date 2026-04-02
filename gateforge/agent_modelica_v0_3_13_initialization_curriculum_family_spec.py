from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_13_initialization_curriculum_taskset import (
    COURSE_STAGE,
    DEFAULT_OUT_DIR as DEFAULT_TASKSET_OUT_DIR,
    FAMILY_ID,
)


SCHEMA_VERSION = "agent_modelica_v0_3_13_initialization_curriculum_family_spec"
DEFAULT_TASKSET = f"{DEFAULT_TASKSET_OUT_DIR}/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_initialization_curriculum_family_spec"
MIN_CURRICULUM_READY_CASES = 8


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def check_family_gate(candidate: dict) -> tuple[bool, str]:
    family_id = _norm(candidate.get("v0_3_13_family_id") or candidate.get("family_id"))
    if family_id == _norm(FAMILY_ID):
        return True, f"family_ok:{family_id}"
    return False, f"family_mismatch:{family_id}"


def check_course_stage_gate(candidate: dict) -> tuple[bool, str]:
    course_stage = _norm(candidate.get("course_stage"))
    if course_stage == _norm(COURSE_STAGE):
        return True, f"course_stage_ok:{course_stage}"
    return False, f"course_stage_mismatch:{course_stage}"


def check_initialization_contract_gate(candidate: dict) -> tuple[bool, str]:
    if _norm(candidate.get("hidden_base_operator")) != "init_equation_sign_flip":
        return False, f"hidden_base_operator_mismatch:{_norm(candidate.get('hidden_base_operator'))}"
    contract = candidate.get("preview_contract")
    if not isinstance(contract, dict):
        return False, "preview_contract_missing"
    if not bool(contract.get("preview_admission")):
        return False, "preview_admission_required"
    if _norm(contract.get("residual_signal_cluster_id")) != "initialization_parameter_recovery":
        return False, f"signal_cluster_mismatch:{_norm(contract.get('residual_signal_cluster_id'))}"
    if not _norm(contract.get("post_rule_residual_stage")).startswith("stage_4_"):
        return False, f"stage_4_initialization_required:{_norm(contract.get('post_rule_residual_stage'))}"
    return True, "initialization_contract_ok"


def check_target_gate(candidate: dict) -> tuple[bool, str]:
    lhs = _norm(candidate.get("v0_3_13_initialization_target_lhs"))
    if lhs:
        return True, f"target_ok:{lhs}"
    return False, "initialization_target_lhs_missing"


def run_gates(candidate: dict) -> dict:
    gates = []
    reasons = []
    for gate_fn, gate_name in [
        (check_family_gate, "family_gate"),
        (check_course_stage_gate, "course_stage_gate"),
        (check_initialization_contract_gate, "initialization_contract_gate"),
        (check_target_gate, "target_gate"),
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


def build_family_summary(candidates: list[dict]) -> dict:
    results = [run_gates(row) for row in candidates]
    admitted = [row for row in results if row["passed"]]
    rejection_summary: dict[str, int] = {}
    for row in results:
        if row["passed"]:
            continue
        for reason in row.get("reasons") or []:
            rejection_summary[reason] = rejection_summary.get(reason, 0) + 1
    lane_status = "EMPTY"
    if results:
        lane_status = "CURRICULUM_READY" if len(admitted) >= MIN_CURRICULUM_READY_CASES else "NEEDS_MORE_GENERATION"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lane_status": lane_status,
        "family_id": FAMILY_ID,
        "total_candidate_count": len(results),
        "admitted_count": len(admitted),
        "rejected_count": len(results) - len(admitted),
        "admitted_task_ids": [row["task_id"] for row in admitted],
        "targets": {"min_curriculum_ready_cases": MIN_CURRICULUM_READY_CASES},
        "rejection_summary": rejection_summary,
        "gate_results": results,
    }


def build_family_summary_from_taskset(*, candidate_taskset_path: str = DEFAULT_TASKSET, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    payload = _load_json(candidate_taskset_path)
    rows = payload.get("tasks")
    candidates = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    summary = build_family_summary(candidates)
    summary["candidate_taskset_path"] = str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path)
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Initialization Curriculum Family Spec",
                "",
                f"- lane_status: `{summary.get('lane_status')}`",
                f"- total_candidate_count: `{summary.get('total_candidate_count')}`",
                f"- admitted_count: `{summary.get('admitted_count')}`",
                "",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the v0.3.13 initialization curriculum family spec.")
    parser.add_argument("--candidate-taskset", default=DEFAULT_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_family_summary_from_taskset(
        candidate_taskset_path=str(args.candidate_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"lane_status": payload.get("lane_status"), "admitted_count": payload.get("admitted_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
