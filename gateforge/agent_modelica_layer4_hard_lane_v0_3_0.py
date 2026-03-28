from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_difficulty_layer_sidecar_builder_v1 import build_sidecar


SCHEMA_VERSION = "agent_modelica_layer4_hard_lane_v0_3_0"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_layer4_hard_lane_v0_3_0"
DEFAULT_FAMILY_SPEC = "artifacts/agent_modelica_layer4_family_spec_v0_3_0/spec.json"

DEFAULT_SOURCE_SPECS = (
    {
        "family_id": "initialization_singularity",
        "family_label": "Initialization Singularity",
        "source_taskset_path": "artifacts/agent_modelica_l4_realism_evidence_v1/challenge/taskset_frozen.json",
        "results_paths": [
            "artifacts/agent_modelica_l4_realism_evidence_v1/main_l5/l4/off/run_results.json",
        ],
        "failure_types": ["initialization_infeasible"],
        "max_tasks": 6,
        "difficulty_layer": "layer_4",
        "dominant_stage_subtype": "stage_4_initialization_singularity",
        "layer_reason": "manual_family_review_initialization_singularity",
    },
    {
        "family_id": "runtime_numerical_instability",
        "family_label": "Runtime Numerical Instability",
        "source_taskset_path": "artifacts/agent_modelica_wave2_1_harder_dynamics_evidence_v1/challenge/taskset_frozen.json",
        "results_paths": [
            "artifacts/agent_modelica_wave2_1_harder_dynamics_evidence_v1/deterministic_on/results.json",
        ],
        "failure_types": ["solver_sensitive_simulate_failure"],
        "max_tasks": 6,
        "difficulty_layer": "layer_4",
        "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
        "layer_reason": "manual_family_review_runtime_numerical_instability",
    },
    {
        "family_id": "hard_multiround_simulate_failure",
        "family_label": "Hard Multi-Round Simulate Failure",
        "source_taskset_path": "artifacts/agent_modelica_multi_round_failure_taskset_v1_devcheck/taskset_frozen.json",
        "results_paths": [
            "artifacts/agent_modelica_multi_round_failure_live_evidence_v1/runs/multi_round_live_baseline_04/baseline_off_live/results.json",
        ],
        "failure_types": [],
        "max_tasks": 18,
        "difficulty_layer": "layer_4",
        "dominant_stage_subtype": "",
        "layer_reason": "manual_family_review_hard_multiround",
    },
)


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


def _default_md_path(out_json: str | Path) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out}.md"


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _norm(value: object) -> str:
    return str(value or "").strip()


def _row_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id"))


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else payload.get("cases")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and _row_id(row)]


def _family_map(family_spec: dict) -> dict[str, dict]:
    rows = family_spec.get("families") if isinstance(family_spec.get("families"), list) else []
    return {
        _norm(row.get("family_id")): row
        for row in rows
        if isinstance(row, dict) and _norm(row.get("family_id"))
    }


def _select_tasks(source_spec: dict) -> tuple[list[dict], dict]:
    source_path = _norm(source_spec.get("source_taskset_path"))
    payload = _load_json(source_path)
    rows = _task_rows(payload)
    failure_filter = {_norm(item).lower() for item in (source_spec.get("failure_types") or []) if _norm(item)}
    selected: list[dict] = []
    for row in rows:
        failure_type = _norm(row.get("failure_type") or row.get("expected_failure_type")).lower()
        if failure_filter and failure_type not in failure_filter:
            continue
        selected.append(dict(row))
    selected.sort(key=lambda row: _row_id(row))
    max_tasks = int(source_spec.get("max_tasks") or 0)
    if max_tasks > 0:
        selected = selected[:max_tasks]
    return selected, payload


def _annotate_task(task: dict, *, source_spec: dict, source_taskset_path: str) -> dict:
    out = dict(task)
    out["v0_3_family_id"] = _norm(source_spec.get("family_id"))
    out["v0_3_family_label"] = _norm(source_spec.get("family_label") or source_spec.get("family_id"))
    out["expected_layer_hint"] = _norm(source_spec.get("difficulty_layer") or "layer_4")
    out["source_taskset_path"] = str(Path(source_taskset_path).resolve())
    out["source_failure_type"] = _norm(task.get("failure_type") or task.get("expected_failure_type"))
    return out


def _build_override_rows(tasks: list[dict], source_specs: list[dict]) -> list[dict]:
    spec_by_family = {_norm(row.get("family_id")): row for row in source_specs}
    rows: list[dict] = []
    for task in tasks:
        task_id = _row_id(task)
        if not task_id:
            continue
        family_id = _norm(task.get("v0_3_family_id"))
        source_spec = spec_by_family.get(family_id, {})
        row = {
            "item_id": task_id,
            "difficulty_layer": _norm(source_spec.get("difficulty_layer") or "layer_4"),
            "layer_reason": _norm(source_spec.get("layer_reason") or "manual_family_review_layer4"),
            "expected_layer_hint": _norm(source_spec.get("difficulty_layer") or "layer_4"),
            "expected_layer_reason": "from_v0_3_layer4_family_source",
        }
        dominant_stage_subtype = _norm(source_spec.get("dominant_stage_subtype"))
        if dominant_stage_subtype:
            row["dominant_stage_subtype"] = dominant_stage_subtype
        rows.append(row)
    return rows


def _collect_results_paths(source_specs: list[dict]) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for source_spec in source_specs:
        for item in source_spec.get("results_paths") or []:
            path = _norm(item)
            if not path or path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return paths


def _success_map(results_paths: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for path in results_paths:
        payload = _load_json(path)
        rows = payload.get("records") if isinstance(payload.get("records"), list) else payload.get("results")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            item_id = _row_id(row)
            if not item_id:
                continue
            if "passed" in row:
                out[item_id] = bool(row.get("passed"))
            elif "success" in row:
                out[item_id] = bool(row.get("success"))
    return out


def _annotation_map(sidecar_payload: dict) -> dict[str, dict]:
    rows = sidecar_payload.get("annotations") if isinstance(sidecar_payload.get("annotations"), list) else []
    return {
        _norm(row.get("item_id")): row
        for row in rows
        if isinstance(row, dict) and _norm(row.get("item_id"))
    }


def _hard_case(task: dict) -> bool:
    if int(task.get("expected_rounds_min") or 0) >= 2:
        return True
    if int(task.get("mock_success_round") or 0) >= 2:
        return True
    if int(task.get("cascade_depth") or 0) >= 2:
        return True
    return bool(task.get("simulate_phase_required"))


def _check_minimum(metric_value: float, threshold: float) -> bool:
    return float(metric_value) >= float(threshold)


def _check_maximum(metric_value: float, threshold: float) -> bool:
    return float(metric_value) <= float(threshold)


def build_layer4_hard_lane(
    *,
    family_spec_path: str = DEFAULT_FAMILY_SPEC,
    out_dir: str = DEFAULT_OUT_DIR,
    source_specs: list[dict] | None = None,
) -> dict:
    family_spec = _load_json(family_spec_path)
    families = _family_map(family_spec)
    out_root = Path(out_dir)
    source_specs = [dict(row) for row in (source_specs or list(DEFAULT_SOURCE_SPECS))]

    selected_tasks: list[dict] = []
    family_sources: list[dict] = []
    selection_reasons: list[str] = []
    missing_sources: list[str] = []

    for source_spec in source_specs:
        family_id = _norm(source_spec.get("family_id"))
        family_row = families.get(family_id, {})
        if not family_row:
            selection_reasons.append(f"unknown_family:{family_id}")
            continue
        if not bool(family_row.get("enabled_for_v0_3_0")):
            selection_reasons.append(f"family_not_enabled:{family_id}")
            continue
        source_taskset_path = _norm(source_spec.get("source_taskset_path"))
        if not Path(source_taskset_path).exists():
            missing_sources.append(source_taskset_path)
            continue
        rows, _payload = _select_tasks(source_spec)
        selected_tasks.extend(_annotate_task(row, source_spec=source_spec, source_taskset_path=source_taskset_path) for row in rows)
        family_sources.append(
            {
                "family_id": family_id,
                "family_label": _norm(source_spec.get("family_label") or family_id),
                "source_taskset_path": str(Path(source_taskset_path).resolve()),
                "selected_task_count": len(rows),
                "results_paths": [str(Path(path).resolve()) for path in (source_spec.get("results_paths") or []) if _norm(path)],
            }
        )

    selected_tasks.sort(key=lambda row: (_norm(row.get("v0_3_family_id")), _row_id(row)))
    taskset_path = out_root / "taskset_frozen.json"
    override_path = out_root / "layer_overrides.json"
    sidecar_path = out_root / "layer_metadata.json"
    summary_path = out_root / "summary.json"
    md_path = Path(_default_md_path(summary_path))

    taskset_payload = {
        "schema_version": "agent_modelica_taskset_frozen_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "lane_id": "layer4_hard_v0_3_0",
        "label": "Layer 4 Hard Lane v0.3.0",
        "task_count": len(selected_tasks),
        "layer4_lane_metadata": {
            "schema_version": SCHEMA_VERSION,
            "family_spec_path": str(Path(family_spec_path).resolve()) if Path(family_spec_path).exists() else str(family_spec_path),
            "family_source_count": len(family_sources),
            "family_sources": family_sources,
        },
        "tasks": selected_tasks,
    }
    _write_json(taskset_path, taskset_payload)

    overrides_payload = {"overrides": _build_override_rows(selected_tasks, source_specs)}
    _write_json(override_path, overrides_payload)

    results_paths = _collect_results_paths(source_specs)
    sidecar_summary = build_sidecar(
        substrate_path=str(taskset_path),
        results_paths=results_paths,
        out_sidecar=str(sidecar_path),
        override_path=str(override_path),
    )
    sidecar_payload = _load_json(sidecar_path)
    annotations = _annotation_map(sidecar_payload)
    success_by_task = _success_map(results_paths)

    family_summaries: list[dict] = []
    overall_status = "PASS"
    for source_spec in source_specs:
        family_id = _norm(source_spec.get("family_id"))
        family_row = families.get(family_id)
        if not isinstance(family_row, dict) or not bool(family_row.get("enabled_for_v0_3_0")):
            continue
        tasks = [row for row in selected_tasks if _norm(row.get("v0_3_family_id")) == family_id]
        task_ids = [_row_id(row) for row in tasks if _row_id(row)]
        ann_rows = [annotations[item_id] for item_id in task_ids if item_id in annotations]
        effective_layer4_count = len([row for row in ann_rows if _norm(row.get("difficulty_layer")) == "layer_4"])
        observed_layer4_count = len(
            [
                row
                for row in ann_rows
                if _norm(row.get("difficulty_layer")) == "layer_4" and _norm(row.get("difficulty_layer_source")) == "observed"
            ]
        )
        stage45_count = len(
            [
                row
                for row in ann_rows
                if _norm(row.get("dominant_stage_subtype"))
                in {"stage_4_initialization_singularity", "stage_5_runtime_numerical_instability"}
            ]
        )
        hard_case_count = len([row for row in tasks if _hard_case(row)])
        success_rows = [success_by_task[item_id] for item_id in task_ids if item_id in success_by_task]
        success_rate_pct = _ratio(len([flag for flag in success_rows if flag]), len(success_rows))
        effective_layer4_share_pct = _ratio(effective_layer4_count, len(ann_rows))
        observed_layer4_share_pct = _ratio(observed_layer4_count, len(ann_rows))
        stage45_share_pct = _ratio(stage45_count, len(ann_rows))
        hard_case_rate_pct = _ratio(hard_case_count, len(tasks))

        checks: list[dict] = []
        family_status = "PASS"
        validation = family_row.get("validation_criterion") if isinstance(family_row.get("validation_criterion"), dict) else {}
        if "min_observed_layer4_share_pct" in validation:
            threshold = float(validation.get("min_observed_layer4_share_pct") or 0.0)
            proxy_used = observed_layer4_count == 0 and effective_layer4_count > 0
            metric_value = effective_layer4_share_pct if proxy_used else observed_layer4_share_pct
            passed = _check_minimum(metric_value, threshold)
            checks.append(
                {
                    "metric": "min_observed_layer4_share_pct",
                    "threshold": threshold,
                    "metric_value_pct": metric_value,
                    "observed_metric_value_pct": observed_layer4_share_pct,
                    "effective_metric_value_pct": effective_layer4_share_pct,
                    "proxy_used": proxy_used,
                    "status": "PASS" if passed else "FAIL",
                }
            )
            if not passed:
                family_status = "FAIL"
        if "min_stage4_stage5_share_pct" in validation:
            threshold = float(validation.get("min_stage4_stage5_share_pct") or 0.0)
            passed = _check_minimum(stage45_share_pct, threshold)
            checks.append(
                {
                    "metric": "min_stage4_stage5_share_pct",
                    "threshold": threshold,
                    "metric_value_pct": stage45_share_pct,
                    "status": "PASS" if passed else "FAIL",
                }
            )
            if not passed:
                family_status = "FAIL"
        if "max_gateforge_success_rate_pct" in validation:
            threshold = float(validation.get("max_gateforge_success_rate_pct") or 0.0)
            passed = bool(success_rows) and _check_maximum(success_rate_pct, threshold)
            checks.append(
                {
                    "metric": "max_gateforge_success_rate_pct",
                    "threshold": threshold,
                    "metric_value_pct": success_rate_pct,
                    "support_count": len(success_rows),
                    "status": "PASS" if passed else "FAIL",
                }
            )
            if not passed:
                family_status = "FAIL"
        if "min_hard_case_rate_pct" in validation:
            threshold = float(validation.get("min_hard_case_rate_pct") or 0.0)
            passed = _check_minimum(hard_case_rate_pct, threshold)
            checks.append(
                {
                    "metric": "min_hard_case_rate_pct",
                    "threshold": threshold,
                    "metric_value_pct": hard_case_rate_pct,
                    "status": "PASS" if passed else "FAIL",
                }
            )
            if not passed:
                family_status = "FAIL"

        if family_status != "PASS":
            overall_status = "FAIL"
        family_summaries.append(
            {
                "family_id": family_id,
                "family_label": _norm(source_spec.get("family_label") or family_id),
                "task_count": len(tasks),
                "effective_layer4_share_pct": effective_layer4_share_pct,
                "observed_layer4_share_pct": observed_layer4_share_pct,
                "stage4_stage5_share_pct": stage45_share_pct,
                "hard_case_rate_pct": hard_case_rate_pct,
                "gateforge_success_rate_pct": success_rate_pct,
                "gateforge_success_support_count": len(success_rows),
                "validation_checks": checks,
                "status": family_status,
            }
        )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if missing_sources else overall_status,
        "lane_id": "layer4_hard_v0_3_0",
        "taskset_path": str(taskset_path.resolve()),
        "sidecar_path": str(sidecar_path.resolve()),
        "override_path": str(override_path.resolve()),
        "family_spec_path": str(Path(family_spec_path).resolve()) if Path(family_spec_path).exists() else str(family_spec_path),
        "task_count": len(selected_tasks),
        "missing_sources": missing_sources,
        "selection_reasons": selection_reasons,
        "sidecar_summary": sidecar_summary,
        "family_sources": family_sources,
        "family_summaries": family_summaries,
    }
    _write_json(summary_path, summary)

    lines = [
        "# Agent Modelica Layer 4 Hard Lane v0.3.0",
        "",
        f"- status: `{summary.get('status')}`",
        f"- task_count: `{summary.get('task_count')}`",
        "",
    ]
    for family in family_summaries:
        lines.append(f"## {family.get('family_label')}")
        lines.append("")
        lines.append(f"- task_count: `{family.get('task_count')}`")
        lines.append(f"- effective_layer4_share_pct: `{family.get('effective_layer4_share_pct')}`")
        lines.append(f"- observed_layer4_share_pct: `{family.get('observed_layer4_share_pct')}`")
        lines.append(f"- stage4_stage5_share_pct: `{family.get('stage4_stage5_share_pct')}`")
        lines.append(f"- hard_case_rate_pct: `{family.get('hard_case_rate_pct')}`")
        lines.append(f"- gateforge_success_rate_pct: `{family.get('gateforge_success_rate_pct')}`")
        lines.append(f"- status: `{family.get('status')}`")
        lines.append("")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the first frozen Layer 4 hard lane for v0.3.0")
    parser.add_argument("--family-spec", default=DEFAULT_FAMILY_SPEC)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    summary = build_layer4_hard_lane(
        family_spec_path=str(args.family_spec),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": summary.get("status"), "task_count": int(summary.get("task_count") or 0)}))
    if summary.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
