from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_structural_singularity_trial_v0_3_1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_structural_singularity_trial_v0_3_1"
DEFAULT_FAMILY_SPEC_PATH = "artifacts/agent_modelica_layer4_family_spec_v0_3_0/spec.json"
DEFAULT_UNDER_TASKSET = "artifacts/agent_modelica_electrical_realism_frozen_taskset_v1/taskset_frozen.json"
DEFAULT_UNDER_FAST_CHECK = "artifacts/agent_modelica_underconstrained_fast_check_v1/summary.json"
DEFAULT_OVER_TASKSET = "artifacts/agent_modelica_wave2_realism_evidence_v1/challenge/taskset_frozen.json"


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


def _task_rows(path: str, *, failure_type: str) -> list[dict]:
    payload = _load_json(path)
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    return [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("failure_type") or "").strip().lower() == failure_type.lower()
    ]


def _manifestation_summary(path: str) -> dict:
    payload = _load_json(path)
    return payload if isinstance(payload, dict) else {}


def _family_spec_row(path: str, family_id: str) -> dict:
    payload = _load_json(path)
    rows = payload.get("families") if isinstance(payload.get("families"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("family_id") or "").strip() == family_id:
            return row
    return {}


def _source_existence_metrics(rows: list[dict]) -> dict:
    source_paths = [Path(str(row.get("source_model_path") or "")) for row in rows if str(row.get("source_model_path") or "").strip()]
    mutant_paths = [Path(str(row.get("mutated_model_path") or "")) for row in rows if str(row.get("mutated_model_path") or "").strip()]
    source_exists = len([p for p in source_paths if p.exists()])
    mutant_exists = len([p for p in mutant_paths if p.exists()])
    return {
        "task_count": len(rows),
        "source_model_path_count": len(source_paths),
        "source_model_exists_count": source_exists,
        "mutated_model_path_count": len(mutant_paths),
        "mutated_model_exists_count": mutant_exists,
        "source_viability_ok": len(rows) > 0 and source_exists == len(source_paths) and mutant_exists == len(mutant_paths),
    }


def build_structural_singularity_trial(
    *,
    out_dir: str = DEFAULT_OUT_DIR,
    family_spec_path: str = DEFAULT_FAMILY_SPEC_PATH,
    under_taskset_path: str = DEFAULT_UNDER_TASKSET,
    under_fast_check_path: str = DEFAULT_UNDER_FAST_CHECK,
    over_taskset_path: str = DEFAULT_OVER_TASKSET,
) -> dict:
    family_row = _family_spec_row(family_spec_path, "structural_singularity")
    under_rows = _task_rows(under_taskset_path, failure_type="underconstrained_system")
    over_rows = _task_rows(over_taskset_path, failure_type="overconstrained_system")
    under_metrics = _source_existence_metrics(under_rows)
    over_metrics = _source_existence_metrics(over_rows)
    under_fast_check = _manifestation_summary(under_fast_check_path)

    reasons: list[str] = []
    if not under_metrics["source_viability_ok"]:
        reasons.append("underconstrained_source_viability_incomplete")
    if not over_metrics["source_viability_ok"]:
        reasons.append("overconstrained_source_viability_incomplete")

    under_stage_match = float(under_fast_check.get("stage_match_rate_pct") or 0.0)
    under_manifestation_ok = str(under_fast_check.get("status") or "").upper() == "PASS"
    if not under_manifestation_ok:
        reasons.append("underconstrained_manifestation_not_confirmed")

    # Current diagnostic taxonomy maps structural balance failures to the stage_2 / layer_2 region.
    # That means the existing in-repo structural families do not naturally satisfy the current
    # structural-singularity family contract of expected_layer_hint=layer_4.
    taxonomy_conflict = True
    reasons.append("current_structural_manifestation_maps_to_stage_2_layer_2")
    reasons.append("structural_singularity_layer_4_contract_not_met_by_existing_tasks")

    decision = "approved_v0_3_1"
    if taxonomy_conflict:
        decision = "rejected_for_current_benchmark_program"
    elif reasons:
        decision = "deferred_v0_3_2"

    candidate_rows = []
    for row in sorted(under_rows[:2] + over_rows[:2], key=lambda item: str(item.get("task_id") or "")):
        out = dict(row)
        out["trial_family"] = "structural_singularity"
        out["expected_structural_stage_subtype"] = "stage_2_structural_balance_reference"
        out["expected_layer_under_current_taxonomy"] = "layer_2"
        candidate_rows.append(out)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "family_id": "structural_singularity",
        "current_family_spec_row": family_row,
        "decision": decision,
        "decision_reasons": reasons,
        "candidate_summary": {
            "underconstrained_metrics": under_metrics,
            "underconstrained_manifestation": {
                "status": under_fast_check.get("status"),
                "total_tasks": int(under_fast_check.get("total_tasks") or 0),
                "pass_count": int(under_fast_check.get("pass_count") or 0),
                "stage_match_rate_pct": under_stage_match,
            },
            "overconstrained_metrics": over_metrics,
            "taxonomy_observation": {
                "expected_structural_stage_subtype": "stage_2_structural_balance_reference",
                "current_default_layer": "layer_2",
                "family_expected_layer_hint": str(family_row.get("expected_layer_hint") or ""),
            },
        },
        "candidate_rows": candidate_rows,
        "official_micro_lane_created": decision == "approved_v0_3_1",
    }

    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    if candidate_rows:
        _write_json(out_root / "candidate_tasks.json", {"tasks": candidate_rows})
    (out_root / "summary.md").write_text(
        "\n".join(
            [
                "# Agent Modelica Structural Singularity Trial v0.3.1",
                "",
                f"- decision: `{payload.get('decision')}`",
                f"- official_micro_lane_created: `{payload.get('official_micro_lane_created')}`",
                f"- reasons: `{','.join(payload.get('decision_reasons') or []) or 'none'}`",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate whether structural singularity is viable for v0.3.1")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--family-spec", default=DEFAULT_FAMILY_SPEC_PATH)
    parser.add_argument("--under-taskset", default=DEFAULT_UNDER_TASKSET)
    parser.add_argument("--under-fast-check", default=DEFAULT_UNDER_FAST_CHECK)
    parser.add_argument("--over-taskset", default=DEFAULT_OVER_TASKSET)
    args = parser.parse_args()
    payload = build_structural_singularity_trial(
        out_dir=str(args.out_dir),
        family_spec_path=str(args.family_spec),
        under_taskset_path=str(args.under_taskset),
        under_fast_check_path=str(args.under_fast_check),
        over_taskset_path=str(args.over_taskset),
    )
    print(json.dumps({"status": payload.get("status"), "decision": payload.get("decision")}))


if __name__ == "__main__":
    main()
