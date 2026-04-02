from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_curriculum_work_order"
DEFAULT_SEED_FAMILY_SPEC = "artifacts/agent_modelica_v0_3_13_seed_family_spec_current/summary.json"
DEFAULT_RUNTIME_FAMILY_SPEC = "artifacts/agent_modelica_v0_3_13_runtime_curriculum_family_spec_current/summary.json"
DEFAULT_PREVIEW_V036 = "artifacts/agent_modelica_v0_3_13_trajectory_preview_v0_3_6_current/summary.json"
DEFAULT_SOURCE_TASKSET_V036 = "artifacts/agent_modelica_post_restore_taskset_v0_3_6_current/taskset.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_curriculum_work_order"


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


def _preview_rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _task_rows(payload: dict) -> dict[str, dict]:
    rows = payload.get("tasks")
    mapping: dict[str, dict] = {}
    if not isinstance(rows, list):
        return mapping
    for row in rows:
        if not isinstance(row, dict):
            continue
        task_id = _norm(row.get("task_id"))
        if task_id:
            mapping[task_id] = row
    return mapping


def _count_excluded_by_operator(*, preview_rows: list[dict], source_rows: dict[str, dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in preview_rows:
        if _norm(row.get("preview_reason")) != "post_rule_success_without_residual":
            continue
        task = source_rows.get(_norm(row.get("task_id")))
        operator = _norm((task or {}).get("hidden_base_operator"))
        if not operator:
            operator = "unknown"
        counts[operator] = counts.get(operator, 0) + 1
    return counts


def build_curriculum_work_order(
    *,
    seed_family_spec_path: str = DEFAULT_SEED_FAMILY_SPEC,
    runtime_family_spec_path: str = DEFAULT_RUNTIME_FAMILY_SPEC,
    preview_v036_path: str = DEFAULT_PREVIEW_V036,
    source_taskset_v036_path: str = DEFAULT_SOURCE_TASKSET_V036,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    seed_spec = _load_json(seed_family_spec_path)
    runtime_spec = _load_json(runtime_family_spec_path)
    preview_v036 = _load_json(preview_v036_path)
    source_v036 = _load_json(source_taskset_v036_path)
    preview_rows = _preview_rows(preview_v036)
    source_rows = _task_rows(source_v036)

    excluded_rows = [row for row in preview_rows if _norm(row.get("preview_reason")) == "post_rule_success_without_residual"]
    include_lanes = []
    if _norm(seed_spec.get("lane_status")) == "SEED_READY":
        include_lanes.append(
            {
                "lane_id": "v0_3_13_seed_lane",
                "status": "ACTIVE",
                "reason": "audited two-step residual seeds remain the canonical initialization+runtime seed set",
                "admitted_count": int(seed_spec.get("admitted_count") or 0),
            }
        )
    if _norm(runtime_spec.get("lane_status")) == "CURRICULUM_READY":
        include_lanes.append(
            {
                "lane_id": "v0_3_13_runtime_curriculum_lane",
                "status": "ACTIVE",
                "reason": "broader v0.3.6 collapse source expands cleanly into runtime multiround curriculum candidates",
                "admitted_count": int(runtime_spec.get("admitted_count") or 0),
            }
        )

    exclude_rules = [
        {
            "rule_id": "exclude_post_rule_success_without_residual",
            "status": "ACTIVE",
            "reason": "cleanup-only success after surface removal does not create a multiround learning opportunity",
            "excluded_case_count": len(excluded_rows),
            "excluded_operator_counts": _count_excluded_by_operator(preview_rows=preview_rows, source_rows=source_rows),
            "excluded_task_ids": [_norm(row.get("task_id")) for row in excluded_rows],
        }
    ]

    next_generation_targets = [
        "Expand the runtime curriculum lane by generating more paired-value collapse cases on additional self-contained models.",
        "Design a new scalable initialization-masking family, because the current broader v0.3.6 source does not reproduce the initialization seeds beyond the audited v0.3.5 set.",
        "Do not spend multiround budget on paired_value_bias_shift until it can be redesigned to leave a residual after deterministic surface cleanup.",
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "include_lanes": include_lanes,
        "exclude_rules": exclude_rules,
        "next_generation_targets": next_generation_targets,
        "evidence": {
            "seed_family_spec_path": str(Path(seed_family_spec_path).resolve()) if Path(seed_family_spec_path).exists() else str(seed_family_spec_path),
            "runtime_family_spec_path": str(Path(runtime_family_spec_path).resolve()) if Path(runtime_family_spec_path).exists() else str(runtime_family_spec_path),
            "preview_v036_path": str(Path(preview_v036_path).resolve()) if Path(preview_v036_path).exists() else str(preview_v036_path),
            "source_taskset_v036_path": str(Path(source_taskset_v036_path).resolve()) if Path(source_taskset_v036_path).exists() else str(source_taskset_v036_path),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.13 Curriculum Work Order",
        "",
        f"- status: `{payload.get('status')}`",
        "",
        "## Include Lanes",
        "",
    ]
    for row in payload.get("include_lanes") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- `{row.get('lane_id')}`: {row.get('reason')}")
    lines.append("")
    lines.append("## Exclude Rules")
    lines.append("")
    for row in payload.get("exclude_rules") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- `{row.get('rule_id')}`: {row.get('reason')}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 curriculum work order.")
    parser.add_argument("--seed-family-spec", default=DEFAULT_SEED_FAMILY_SPEC)
    parser.add_argument("--runtime-family-spec", default=DEFAULT_RUNTIME_FAMILY_SPEC)
    parser.add_argument("--preview-v036", default=DEFAULT_PREVIEW_V036)
    parser.add_argument("--source-taskset-v036", default=DEFAULT_SOURCE_TASKSET_V036)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_curriculum_work_order(
        seed_family_spec_path=str(args.seed_family_spec),
        runtime_family_spec_path=str(args.runtime_family_spec),
        preview_v036_path=str(args.preview_v036),
        source_taskset_v036_path=str(args.source_taskset_v036),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "include_lane_count": len(payload.get("include_lanes") or [])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
