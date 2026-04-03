from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_19_common import (
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    build_source_specs,
    now_utc,
    norm,
    replacement_audit,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_taskset"


def build_v0319_taskset(*, out_dir: str = str(DEFAULT_TASKSET_OUT_DIR)) -> dict:
    tasks: list[dict] = []
    family_counts: dict[str, int] = {}
    placement_counts: dict[str, int] = {}
    for spec in build_source_specs():
        for variant in spec.get("variants") or []:
            replacements = [(row[0], row[1]) for row in (variant.get("replacements") or [])]
            mutated_model_text, audit = replacement_audit(norm(spec.get("source_model_text")), replacements)
            task_id = f"v0319_{norm(spec.get('source_id'))}__{norm(variant.get('variant_id'))}"
            task = {
                "schema_version": SCHEMA_VERSION,
                "generated_at_utc": now_utc(),
                "task_id": task_id,
                "complexity_tier": norm(spec.get("complexity_tier")),
                "model_name": norm(spec.get("model_name")),
                "source_model_text": norm(spec.get("source_model_text")),
                "mutated_model_text": mutated_model_text,
                "declared_failure_type": "model_check_error",
                "expected_stage": "check",
                "v0_3_19_source_id": norm(spec.get("source_id")),
                "v0_3_19_variant_id": norm(variant.get("variant_id")),
                "v0_3_19_placement_kind": norm(variant.get("placement_kind")),
                "v0_3_19_mutation_shape": norm(variant.get("mutation_shape")),
                "v0_3_19_target_action_type": "component_api_alignment",
                "v0_3_19_focal_component": norm(variant.get("focal_component")),
                "v0_3_19_same_component_dual_mismatch": norm(variant.get("placement_kind")) == "same_component_dual_mismatch",
                "v0_3_19_expected_first_error_signature_hint": norm(variant.get("expected_first_error_signature_hint")),
                "v0_3_19_expected_second_error_signature_hint": norm(variant.get("expected_second_error_signature_hint")),
                "mutation_spec": {
                    "placement_kind": norm(variant.get("placement_kind")),
                    "mutation_shape": norm(variant.get("mutation_shape")),
                    "focal_component": norm(variant.get("focal_component")),
                    "replacement_audit": audit,
                },
            }
            tasks.append(task)
            family_counts[task["v0_3_19_mutation_shape"]] = family_counts.get(task["v0_3_19_mutation_shape"], 0) + 1
            placement_counts[task["v0_3_19_placement_kind"]] = placement_counts.get(task["v0_3_19_placement_kind"], 0) + 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if tasks else "EMPTY",
        "task_count": len(tasks),
        "family_counts": family_counts,
        "placement_counts": placement_counts,
        "same_component_task_count": sum(1 for row in tasks if bool(row.get("v0_3_19_same_component_dual_mismatch"))),
        "neighbor_component_task_count": sum(1 for row in tasks if norm(row.get("v0_3_19_placement_kind")) == "neighbor_component_dual_mismatch"),
        "tasks": tasks,
    }
    out_root = Path(out_dir)
    for task in tasks:
        write_json(out_root / "tasks" / f"{task['task_id']}.json", task)
    write_json(out_root / "taskset.json", payload)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.19 Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- task_count: `{payload.get('task_count')}`",
                f"- same_component_task_count: `{payload.get('same_component_task_count')}`",
                f"- neighbor_component_task_count: `{payload.get('neighbor_component_task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.19 stage_2 API alignment taskset.")
    parser.add_argument("--out-dir", default=str(DEFAULT_TASKSET_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0319_taskset(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
