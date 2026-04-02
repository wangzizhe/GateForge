from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_13_seed_taskset import (
    COURSE_STAGE,
    DEFAULT_OUT_DIR as DEFAULT_TASKSET_OUT_DIR,
    FAMILY_INITIALIZATION,
    FAMILY_RUNTIME,
)


SCHEMA_VERSION = "agent_modelica_v0_3_13_seed_family_spec"
DEFAULT_TASKSET = f"{DEFAULT_TASKSET_OUT_DIR}/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_seed_family_spec"
MIN_TOTAL_SEEDS = 8
MIN_PER_FAMILY = 3
REQUIRED_FAMILIES = (FAMILY_RUNTIME, FAMILY_INITIALIZATION)


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


def check_course_stage_gate(candidate: dict) -> tuple[bool, str]:
    stage = _norm(candidate.get("course_stage"))
    if stage == _norm(COURSE_STAGE):
        return True, f"course_stage_ok:{stage}"
    return False, f"course_stage_mismatch:{stage}"


def check_preview_contract_gate(candidate: dict) -> tuple[bool, str]:
    contract = candidate.get("preview_contract")
    if not isinstance(contract, dict):
        return False, "preview_contract_missing"
    if not bool(contract.get("surface_fixable_by_rule")):
        return False, "surface_fixable_by_rule_required"
    if not bool(contract.get("preview_admission")):
        return False, "preview_admission_required"
    if not _norm(contract.get("post_rule_residual_stage")).startswith(("stage_4_", "stage_5_")):
        return False, f"late_residual_stage_required:{_norm(contract.get('post_rule_residual_stage'))}"
    return True, "preview_contract_ok"


def check_family_gate(candidate: dict) -> tuple[bool, str]:
    family_id = _norm(candidate.get("v0_3_13_family_id"))
    if family_id in {_norm(x) for x in REQUIRED_FAMILIES}:
        return True, f"family_ok:{family_id}"
    return False, f"family_not_supported:{family_id}"


def check_success_pattern_gate(candidate: dict) -> tuple[bool, str]:
    resolution_path = _norm(candidate.get("resolution_path"))
    rounds_used = int(candidate.get("rounds_used") or 0)
    if resolution_path != "rule_then_llm":
        return False, f"resolution_path_not_supported:{resolution_path}"
    if rounds_used < 3:
        return False, f"rounds_used_below_multiround_threshold:{rounds_used}"
    return True, "success_pattern_ok"


def run_seed_gates(candidate: dict) -> dict:
    gates = []
    reasons = []
    for gate_fn, gate_name in [
        (check_course_stage_gate, "course_stage_gate"),
        (check_preview_contract_gate, "preview_contract_gate"),
        (check_family_gate, "family_gate"),
        (check_success_pattern_gate, "success_pattern_gate"),
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


def _family_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        family_id = _norm(row.get("v0_3_13_family_id"))
        if not family_id:
            continue
        counts[family_id] = counts.get(family_id, 0) + 1
    return counts


def build_family_summary(candidates: list[dict]) -> dict:
    results = [run_seed_gates(row) for row in candidates]
    admitted = [row for row in results if row["passed"]]
    admitted_task_ids = {str(row["task_id"] or "") for row in admitted}
    admitted_candidates = [row for row in candidates if str(row.get("task_id") or "") in admitted_task_ids]
    family_counts = _family_counts(admitted_candidates)
    missing_families = [family_id for family_id in REQUIRED_FAMILIES if int(family_counts.get(family_id, 0)) < MIN_PER_FAMILY]
    rejection_summary: dict[str, int] = {}
    for row in results:
        if row["passed"]:
            continue
        for reason in row.get("reasons") or []:
            rejection_summary[reason] = rejection_summary.get(reason, 0) + 1
    lane_status = "EMPTY"
    if results:
        if len(admitted) >= MIN_TOTAL_SEEDS and not missing_families:
            lane_status = "SEED_READY"
        else:
            lane_status = "NEEDS_MORE_SEEDS"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lane_status": lane_status,
        "total_candidate_count": len(results),
        "admitted_count": len(admitted),
        "rejected_count": len(results) - len(admitted),
        "family_counts": family_counts,
        "targets": {
            "min_total_seeds": MIN_TOTAL_SEEDS,
            "min_per_family": MIN_PER_FAMILY,
            "required_families": list(REQUIRED_FAMILIES),
            "missing_families": missing_families,
        },
        "admitted_task_ids": [row["task_id"] for row in admitted],
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
                "# v0.3.13 Seed Family Spec",
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
    parser = argparse.ArgumentParser(description="Evaluate the v0.3.13 synthetic seed family spec.")
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
