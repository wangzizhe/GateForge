from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_layer4_generation_workorder_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_layer4_generation_workorder_v0_3_2"
DEFAULT_GENERATION_PRIORITY_SUMMARY = "artifacts/agent_modelica_layer4_generation_priority_v0_3_2/summary.json"
DEFAULT_EXPANSION_TASKSET = "artifacts/agent_modelica_planner_sensitive_expansion_v0_3_2/taskset_candidates.json"
DEFAULT_MULTI_ROUND_MANIFEST = "assets_private/agent_modelica_multi_round_failure_pack_v1/manifest.json"
DEFAULT_WAVE2_MANIFEST = "assets_private/agent_modelica_wave2_1_harder_dynamics_pack_v1/manifest.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else payload.get("cases")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _manifest_models(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for library in payload.get("libraries") or []:
        if not isinstance(library, dict):
            continue
        library_id = _norm(library.get("library_id"))
        for model in library.get("allowed_models") or []:
            if not isinstance(model, dict):
                continue
            rows.append(
                {
                    "library_id": library_id,
                    "model_id": _norm(model.get("model_id")),
                    "qualified_model_name": _norm(model.get("qualified_model_name")),
                }
            )
    return rows


def _candidate_focus_rows(candidate_rows: list[dict], family_id: str) -> list[dict]:
    rows: list[dict] = []
    for row in candidate_rows:
        if _norm(row.get("v0_3_family_id")) != family_id:
            continue
        source_meta = row.get("source_meta") if isinstance(row.get("source_meta"), dict) else {}
        library_id = _norm(source_meta.get("library_id") or row.get("source_library"))
        model_id = _norm(source_meta.get("model_id") or row.get("origin_task_id"))
        if family_id == "initialization_singularity" and not model_id:
            model_id = _norm(row.get("origin_task_id") or row.get("task_id"))
        if not library_id and family_id == "initialization_singularity":
            library_id = "electrical_realism"
        if not model_id:
            continue
        rows.append(
            {
                "task_id": _norm(row.get("task_id")),
                "library_id": library_id,
                "model_id": model_id,
                "failure_type": _norm(row.get("failure_type")),
            }
        )
    rows.sort(key=lambda row: (row["library_id"], row["model_id"], row["task_id"]))
    return rows


def _generator_config(family_id: str) -> dict:
    if family_id == "hard_multiround_simulate_failure":
        return {
            "generator_module": "gateforge.agent_modelica_multi_round_failure_taskset_v1",
            "driver_script": "scripts/run_agent_modelica_multi_round_failure_evidence_v1.sh",
            "manifest_path": DEFAULT_MULTI_ROUND_MANIFEST,
            "failure_types": ["cascading_structural_failure", "coupled_conflict_failure"],
            "note": "prefer family members that keep simulate-phase complexity after the first local fix",
        }
    if family_id == "runtime_numerical_instability":
        return {
            "generator_module": "gateforge.agent_modelica_wave2_1_harder_dynamics_taskset_v1",
            "driver_script": "scripts/run_agent_modelica_wave2_1_harder_dynamics_live_evidence_v1.sh",
            "manifest_path": DEFAULT_WAVE2_MANIFEST,
            "failure_types": ["solver_sensitive_simulate_failure"],
            "note": "prefer solver-sensitive cases that already look multi-round in source evidence",
        }
    return {
        "generator_module": "gateforge.agent_modelica_electrical_mutant_taskset_v0",
        "driver_script": "scripts/run_agent_modelica_electrical_realism_frozen_taskset_v1.sh",
        "manifest_path": "",
        "failure_types": ["initialization_infeasible"],
        "note": "treat as secondary after planner-sensitive families because current evidence is hard but not yet planner-shaped",
    }


def _candidate_pool_from_manifest(manifest_path: str, observed_rows: list[dict]) -> list[dict]:
    if not _norm(manifest_path):
        return []
    payload = _load_json(manifest_path)
    manifest_rows = _manifest_models(payload)
    seen = {(row["library_id"], row["model_id"]) for row in observed_rows}
    out = [row for row in manifest_rows if (row["library_id"], row["model_id"]) not in seen]
    out.sort(key=lambda row: (row["library_id"], row["model_id"]))
    return out


def build_generation_workorder(
    *,
    generation_priority_summary_path: str = DEFAULT_GENERATION_PRIORITY_SUMMARY,
    expansion_taskset_path: str = DEFAULT_EXPANSION_TASKSET,
) -> dict:
    priority_payload = _load_json(generation_priority_summary_path)
    expansion_taskset = _load_json(expansion_taskset_path)
    candidate_rows = _task_rows(expansion_taskset)
    family_rows = [row for row in (priority_payload.get("family_priorities") or []) if isinstance(row, dict)]

    work_orders: list[dict] = []
    for family_row in family_rows:
        family_id = _norm(family_row.get("family_id"))
        generator = _generator_config(family_id)
        focus_rows = _candidate_focus_rows(candidate_rows, family_id)
        manifest_candidates = _candidate_pool_from_manifest(_norm(generator.get("manifest_path")), focus_rows)
        failure_types = [str(item) for item in (generator.get("failure_types") or []) if _norm(item)]
        work_orders.append(
            {
                "family_id": family_id,
                "family_label": _norm(family_row.get("family_label") or family_id),
                "priority_bucket": _norm(family_row.get("priority_bucket")),
                "recommended_new_task_target": int(family_row.get("recommended_new_task_target") or 0),
                "generator_module": _norm(generator.get("generator_module")),
                "driver_script": _norm(generator.get("driver_script")),
                "manifest_path": _norm(generator.get("manifest_path")),
                "failure_types": failure_types,
                "focus_models_currently_observed": focus_rows,
                "additional_manifest_models_not_yet_observed": manifest_candidates[:8],
                "execution_note": _norm(generator.get("note")),
                "command_hint": _build_command_hint(
                    family_id=family_id,
                    driver_script=_norm(generator.get("driver_script")),
                    manifest_path=_norm(generator.get("manifest_path")),
                    failure_types=failure_types,
                ),
            }
        )

    priority_1 = [row for row in work_orders if _norm(row.get("priority_bucket")) == "priority_1_generate_now"]
    priority_2 = [row for row in work_orders if _norm(row.get("priority_bucket")) == "priority_2_generate_after_p1"]
    next_actions = []
    if priority_1:
        next_actions.append("Execute the priority_1 work orders first and rerun planner-sensitive expansion.")
    if priority_2:
        next_actions.append("Keep priority_2 work orders queued until the first rerun shows whether the freeze-ready gap shrank materially.")
    next_actions.append("After new mutation generation, rerun the resolution audit and refresh the Track C slice note before any comparative freeze.")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "READY_FOR_EXECUTION" if priority_1 else "READY_FOR_REVIEW",
        "freeze_ready_gap": int(priority_payload.get("freeze_ready_gap") or 0),
        "work_orders": work_orders,
        "next_actions": next_actions,
    }


def _build_command_hint(*, family_id: str, driver_script: str, manifest_path: str, failure_types: list[str]) -> str:
    if family_id == "hard_multiround_simulate_failure":
        return (
            f"GATEFORGE_AGENT_MULTI_ROUND_FAILURE_MANIFEST={manifest_path} "
            f"bash {driver_script}"
        )
    if family_id == "runtime_numerical_instability":
        return (
            f"GATEFORGE_AGENT_WAVE2_1_HARDER_DYNAMICS_MANIFEST={manifest_path} "
            f"bash {driver_script}"
        )
    failure_csv = ",".join(failure_types)
    return f"GATEFORGE_AGENT_ELECTRICAL_REALISM_FAILURE_TYPES={failure_csv} bash {driver_script}"


def render_markdown(payload: dict) -> str:
    lines = [
        "# Layer 4 Generation Workorder v0.3.2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- freeze_ready_gap: `{payload.get('freeze_ready_gap')}`",
        "",
    ]
    for row in payload.get("work_orders") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"## {row.get('family_label')}")
        lines.append("")
        lines.append(f"- priority_bucket: `{row.get('priority_bucket')}`")
        lines.append(f"- recommended_new_task_target: `{row.get('recommended_new_task_target')}`")
        lines.append(f"- generator_module: `{row.get('generator_module')}`")
        lines.append(f"- driver_script: `{row.get('driver_script')}`")
        if _norm(row.get("manifest_path")):
            lines.append(f"- manifest_path: `{row.get('manifest_path')}`")
        lines.append(f"- command_hint: `{row.get('command_hint')}`")
        lines.append(f"- execution_note: {row.get('execution_note')}")
        focus_rows = row.get("focus_models_currently_observed") if isinstance(row.get("focus_models_currently_observed"), list) else []
        if focus_rows:
            for item in focus_rows:
                lines.append(f"- focus_model: `{item.get('library_id')}/{item.get('model_id')}` from `{item.get('task_id')}`")
        extra_rows = row.get("additional_manifest_models_not_yet_observed") if isinstance(row.get("additional_manifest_models_not_yet_observed"), list) else []
        if extra_rows:
            for item in extra_rows:
                lines.append(f"- extra_manifest_model: `{item.get('library_id')}/{item.get('model_id')}`")
        lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    for index, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{index}. {action}")
    lines.append("")
    return "\n".join(lines)


def run_generation_workorder(
    *,
    generation_priority_summary_path: str = DEFAULT_GENERATION_PRIORITY_SUMMARY,
    expansion_taskset_path: str = DEFAULT_EXPANSION_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = build_generation_workorder(
        generation_priority_summary_path=generation_priority_summary_path,
        expansion_taskset_path=expansion_taskset_path,
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build executable work orders from the v0.3.2 harder Layer 4 generation priorities.")
    parser.add_argument("--generation-priority-summary", default=DEFAULT_GENERATION_PRIORITY_SUMMARY)
    parser.add_argument("--expansion-taskset", default=DEFAULT_EXPANSION_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = run_generation_workorder(
        generation_priority_summary_path=str(args.generation_priority_summary),
        expansion_taskset_path=str(args.expansion_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "work_order_count": len(payload.get("work_orders") or [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
