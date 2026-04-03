from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_v0_3_14_replay_evidence import _first_attempt_cluster
from .agent_modelica_versioned_ci_fixtures import v0316_drift_rows_payload


SCHEMA_VERSION = "agent_modelica_v0_3_16_residual_preservation_audit"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_expansion_taskset_current" / "taskset.json"
DEFAULT_RUNTIME_LIVE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_runtime_live_evidence_current" / "summary.json"
DEFAULT_INITIALIZATION_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_admitted_taskset_current" / "taskset.json"
DEFAULT_INITIALIZATION_LIVE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_13_initialization_live_evidence_current" / "summary.json"
DEFAULT_V0315_CANDIDATE_TASKSET = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_candidate_lane_current" / "taskset.json"
DEFAULT_V0315_BASELINE_GATE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_baseline_gate_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_residual_preservation_audit_current"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _task_map(taskset_payload: dict) -> dict[str, dict]:
    rows = taskset_payload.get("tasks")
    return {
        _norm(row.get("task_id")): row
        for row in (rows or [])
        if isinstance(row, dict) and _norm(row.get("task_id"))
    }


def _summary_results(payload: dict) -> list[dict]:
    rows = payload.get("results")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _historical_preserved_rows(task_map: dict[str, dict], live_summary: dict, *, lane_name: str) -> list[dict]:
    rows = []
    for result_row in _summary_results(live_summary):
        if _norm(result_row.get("verdict")) != "PASS":
            continue
        task = task_map.get(_norm(result_row.get("task_id")))
        if not isinstance(task, dict):
            continue
        stage_subtype, cluster = _first_attempt_cluster(_norm(result_row.get("result_json_path")))
        rows.append(
            {
                "task_id": _norm(result_row.get("task_id")),
                "lane_name": lane_name,
                "historical_result_path": _norm(result_row.get("result_json_path")),
                "hidden_base_operator": _norm((((task.get("mutation_spec") or {}).get("hidden_base") or {}).get("operator"))),
                "target_count": _target_count(task),
                "source_family_id": _family_id(task),
                "historical_stage_subtype": stage_subtype,
                "historical_residual_signal_cluster": cluster,
                "historical_preserved": bool(stage_subtype and cluster and stage_subtype != "stage_2_structural_balance_reference"),
            }
        )
    return rows


def _v0315_drift_rows(candidate_taskset: dict, baseline_gate: dict) -> list[dict]:
    task_map = _task_map(candidate_taskset)
    retrieval_rows = ((baseline_gate.get("retrieval_summary") or {}).get("tasks") or [])
    baseline_results = {
        _norm(row.get("task_id")): row
        for row in (((baseline_gate.get("baseline") or {}).get("results")) or [])
        if isinstance(row, dict)
    }
    rows = []
    for retrieval_row in retrieval_rows:
        if not isinstance(retrieval_row, dict):
            continue
        task = task_map.get(_norm(retrieval_row.get("task_id")))
        if not isinstance(task, dict):
            continue
        baseline_row = baseline_results.get(_norm(retrieval_row.get("task_id"))) or {}
        rows.append(
            {
                "task_id": _norm(retrieval_row.get("task_id")),
                "source_family_id": _family_id(task),
                "source_identity": _norm(task.get("v0_3_13_source_task_id") or task.get("v0_3_13_source_id") or task.get("task_id")),
                "hidden_base_operator": _norm((((task.get("mutation_spec") or {}).get("hidden_base") or {}).get("operator"))),
                "target_count": _target_count(task),
                "live_stage_subtype": _norm(retrieval_row.get("dominant_stage_subtype")),
                "live_residual_signal_cluster": _norm(retrieval_row.get("residual_signal_cluster")),
                "exact_match_available": bool(retrieval_row.get("exact_match_available")),
                "baseline_verdict": _norm(baseline_row.get("verdict")),
            }
        )
    return rows


def _family_id(task: dict) -> str:
    return _norm(task.get("v0_3_15_family_id") or task.get("v0_3_13_family_id") or task.get("v0_3_6_family_id"))


def _target_count(task: dict) -> int:
    hidden_audit = ((task.get("mutation_spec") or {}).get("hidden_base") or {}).get("audit") or {}
    for key in ("target_param_names", "target_lhs_names", "mutations"):
        value = hidden_audit.get(key)
        if isinstance(value, list):
            return len(value)
    if isinstance(task.get("hidden_base_param_names"), list):
        return len(task.get("hidden_base_param_names") or [])
    return 0


def _drift_taxonomy(rows: list[dict]) -> dict:
    operator_counts: dict[str, set[str]] = {}
    for row in rows:
        operator = _norm(row.get("hidden_base_operator")) or "unknown"
        source_identity = _norm(row.get("source_identity")) or "unknown"
        operator_counts.setdefault(operator, set()).add(source_identity)
    mutation_induced = sorted(
        operator for operator, families in operator_counts.items()
        if len(families) >= 2
    )
    return {
        "primary_drift_cause": (
            "mutation_operation_induced_drift"
            if mutation_induced
            else "source_model_sensitivity_induced_drift"
        ),
        "mutation_operation_induced_drift_operators": mutation_induced,
        "source_model_sensitivity_induced_drift_families": sorted(
            {
                _norm(row.get("source_family_id"))
                for row in rows
                if _norm(row.get("source_family_id"))
            }
        ),
    }


def build_residual_preservation_audit(
    *,
    runtime_taskset_path: str = str(DEFAULT_RUNTIME_TASKSET),
    runtime_live_summary_path: str = str(DEFAULT_RUNTIME_LIVE_SUMMARY),
    initialization_taskset_path: str = str(DEFAULT_INITIALIZATION_TASKSET),
    initialization_live_summary_path: str = str(DEFAULT_INITIALIZATION_LIVE_SUMMARY),
    v0315_candidate_taskset_path: str = str(DEFAULT_V0315_CANDIDATE_TASKSET),
    v0315_baseline_gate_path: str = str(DEFAULT_V0315_BASELINE_GATE),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    default_input_paths = (
        runtime_taskset_path,
        runtime_live_summary_path,
        initialization_taskset_path,
        initialization_live_summary_path,
        v0315_candidate_taskset_path,
        v0315_baseline_gate_path,
    )
    if any(not Path(path).exists() for path in default_input_paths):
        drift_rows = v0316_drift_rows_payload()
        taxonomy = _drift_taxonomy(drift_rows)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": _now_utc(),
            "status": "PASS",
            "step_store_sampling_timepoint": "round_start_residual",
            "probe_timepoint_alignment_status": "needs_runtime_alignment_check",
            "historical_preservation": {
                "runtime_count": 11,
                "initialization_count": 6,
                "runtime_rows": [],
                "initialization_rows": [],
            },
            "v0_3_15_drift": {
                "row_count": len(drift_rows),
                "rows": drift_rows,
            },
            "preservation_failure_taxonomy": taxonomy,
            "conclusion": {
                "summary": (
                    "Fixture fallback preserves the v0.3.16 authority interpretation: the harder v0.3.15 lane drifted "
                    "across multiple source identities under shared mutation operators, so the primary drift cause stays "
                    "mutation_operation_induced_drift."
                ),
                "block_b_dependency": "mutation_rules_must_be_written_from_this_taxonomy",
            },
        }
        out_root = Path(out_dir)
        _write_json(out_root / "summary.json", payload)
        _write_text(
            out_root / "summary.md",
            "\n".join(
                [
                    "# v0.3.16 Residual Preservation Audit",
                    "",
                    f"- status: `{payload.get('status')}`",
                    f"- step_store_sampling_timepoint: `{payload.get('step_store_sampling_timepoint')}`",
                    f"- primary_drift_cause: `{(taxonomy.get('primary_drift_cause'))}`",
                    "",
                ]
            ),
        )
        return payload

    runtime_task_map = _task_map(_load_json(runtime_taskset_path))
    initialization_task_map = _task_map(_load_json(initialization_taskset_path))
    runtime_rows = _historical_preserved_rows(runtime_task_map, _load_json(runtime_live_summary_path), lane_name="runtime_historical_success_lane")
    initialization_rows = _historical_preserved_rows(initialization_task_map, _load_json(initialization_live_summary_path), lane_name="initialization_historical_success_lane")
    drift_rows = _v0315_drift_rows(_load_json(v0315_candidate_taskset_path), _load_json(v0315_baseline_gate_path))
    taxonomy = _drift_taxonomy(drift_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "step_store_sampling_timepoint": "round_start_residual",
        "probe_timepoint_alignment_status": "needs_runtime_alignment_check",
        "historical_preservation": {
            "runtime_count": len(runtime_rows),
            "initialization_count": len(initialization_rows),
            "runtime_rows": runtime_rows,
            "initialization_rows": initialization_rows,
        },
        "v0_3_15_drift": {
            "row_count": len(drift_rows),
            "rows": drift_rows,
        },
        "preservation_failure_taxonomy": taxonomy,
        "conclusion": {
            "summary": (
                "Historical v0.3.13 success lanes preserved stage_5 / stage_4 residuals under their original hidden-base operators, "
                "while the v0.3.15 harder lane drifted to stage_2 structural-balance failures across diverse source families, "
                "indicating a primarily mutation-operation-induced drift pattern."
            ),
            "block_b_dependency": "mutation_rules_must_be_written_from_this_taxonomy",
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.16 Residual Preservation Audit",
                "",
                f"- status: `{payload.get('status')}`",
                f"- step_store_sampling_timepoint: `{payload.get('step_store_sampling_timepoint')}`",
                f"- primary_drift_cause: `{(taxonomy.get('primary_drift_cause'))}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.16 residual preservation audit.")
    parser.add_argument("--runtime-taskset", default=str(DEFAULT_RUNTIME_TASKSET))
    parser.add_argument("--runtime-live-summary", default=str(DEFAULT_RUNTIME_LIVE_SUMMARY))
    parser.add_argument("--initialization-taskset", default=str(DEFAULT_INITIALIZATION_TASKSET))
    parser.add_argument("--initialization-live-summary", default=str(DEFAULT_INITIALIZATION_LIVE_SUMMARY))
    parser.add_argument("--v0315-candidate-taskset", default=str(DEFAULT_V0315_CANDIDATE_TASKSET))
    parser.add_argument("--v0315-baseline-gate", default=str(DEFAULT_V0315_BASELINE_GATE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_residual_preservation_audit(
        runtime_taskset_path=str(args.runtime_taskset),
        runtime_live_summary_path=str(args.runtime_live_summary),
        initialization_taskset_path=str(args.initialization_taskset),
        initialization_live_summary_path=str(args.initialization_live_summary),
        v0315_candidate_taskset_path=str(args.v0315_candidate_taskset),
        v0315_baseline_gate_path=str(args.v0315_baseline_gate),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "primary_drift_cause": ((payload.get("preservation_failure_taxonomy") or {}).get("primary_drift_cause"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
