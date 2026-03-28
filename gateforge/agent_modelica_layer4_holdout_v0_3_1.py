from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_difficulty_layer_summary_v1 import build_summary


SCHEMA_VERSION = "agent_modelica_layer4_holdout_v0_3_1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_layer4_holdout_v0_3_1"
DEFAULT_SOURCE_TASKSET = "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/taskset_frozen.json"
DEFAULT_SOURCE_SIDECAR = "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/layer_metadata.json"
DEFAULT_BASE_SPEC = "artifacts/agent_modelica_difficulty_layer_v0_3_0/spec.json"
DEFAULT_BASE_SUMMARY = "artifacts/agent_modelica_difficulty_layer_v0_3_0/summary.json"


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _task_id(row: dict) -> str:
    return str(row.get("task_id") or "").strip()


def _annotation_rows(payload: dict) -> list[dict]:
    rows = payload.get("annotations") if isinstance(payload.get("annotations"), list) else []
    return [row for row in rows if isinstance(row, dict) and str(row.get("item_id") or "").strip()]


def build_layer4_holdout_v0_3_1(
    *,
    out_dir: str = DEFAULT_OUT_DIR,
    source_taskset_path: str = DEFAULT_SOURCE_TASKSET,
    source_sidecar_path: str = DEFAULT_SOURCE_SIDECAR,
    base_spec_path: str = DEFAULT_BASE_SPEC,
    base_summary_path: str = DEFAULT_BASE_SUMMARY,
) -> dict:
    source_taskset = _load_json(source_taskset_path)
    source_sidecar = _load_json(source_sidecar_path)
    base_spec = _load_json(base_spec_path)
    base_summary = _load_json(base_summary_path)
    tasks = source_taskset.get("tasks") if isinstance(source_taskset.get("tasks"), list) else []
    holdout_tasks = [dict(row) for row in tasks if isinstance(row, dict) and str(row.get("split") or "").strip().lower() == "holdout"]
    holdout_ids = {_task_id(row) for row in holdout_tasks if _task_id(row)}
    annotations = _annotation_rows(source_sidecar)
    holdout_annotations = [dict(row) for row in annotations if str(row.get("item_id") or "").strip() in holdout_ids]

    family_counts: dict[str, int] = {}
    for row in holdout_tasks:
        family = str(row.get("v0_3_family_id") or "unknown_family").strip()
        family_counts[family] = int(family_counts.get(family, 0)) + 1

    out_root = Path(out_dir)
    taskset_path = out_root / "taskset_frozen.json"
    sidecar_path = out_root / "layer_metadata.json"
    refresh_spec = {
        "lanes": [
            *[dict(row) for row in (base_spec.get("lanes") or []) if isinstance(row, dict)],
            {
                "lane_id": "layer4_holdout_v0_3_1",
                "label": "Layer 4 Holdout v0.3.1",
                "sidecar": str(sidecar_path.resolve()),
            },
        ]
    }

    _write_json(
        taskset_path,
        {
            "schema_version": "agent_modelica_taskset_frozen_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "lane_id": "layer4_holdout_v0_3_1",
            "label": "Layer 4 Holdout v0.3.1",
            "source_taskset_path": str(Path(source_taskset_path).resolve()) if Path(source_taskset_path).exists() else str(source_taskset_path),
            "task_count": len(holdout_tasks),
            "tasks": holdout_tasks,
        },
    )
    _write_json(
        sidecar_path,
        {
            "schema_version": "agent_modelica_difficulty_layer_sidecar_builder_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "substrate_path": str(taskset_path.resolve()),
            "substrate_kind": "taskset",
            "annotations": holdout_annotations,
            "summary": {
                "total_items": len(holdout_annotations),
                "observed_count": len([row for row in holdout_annotations if str(row.get("difficulty_layer_source") or "") == "observed"]),
                "override_count": len([row for row in holdout_annotations if str(row.get("difficulty_layer_source") or "") == "override"]),
                "inferred_count": len([row for row in holdout_annotations if str(row.get("difficulty_layer_source") or "") == "inferred"]),
                "layer_counts": {"layer_4": len([row for row in holdout_annotations if str(row.get("difficulty_layer") or "") == "layer_4"])},
            },
        },
    )

    refresh_summary = build_summary(refresh_spec)
    _write_json(out_root / "refresh_spec.json", refresh_spec)
    _write_json(out_root / "refresh_summary.json", refresh_summary)

    before_counts = (
        (base_summary.get("coverage_gap") if isinstance(base_summary.get("coverage_gap"), dict) else {}).get("aggregate_layer_counts")
        if isinstance((base_summary.get("coverage_gap") if isinstance(base_summary.get("coverage_gap"), dict) else {}), dict)
        else {}
    ) or {}
    after_counts = (
        (refresh_summary.get("coverage_gap") if isinstance(refresh_summary.get("coverage_gap"), dict) else {}).get("aggregate_layer_counts")
        if isinstance((refresh_summary.get("coverage_gap") if isinstance(refresh_summary.get("coverage_gap"), dict) else {}), dict)
        else {}
    ) or {}
    before_layer4 = int(before_counts.get("layer_4") or 0)
    after_layer4 = int(after_counts.get("layer_4") or 0)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if holdout_tasks and holdout_annotations else "FAIL",
        "task_count": len(holdout_tasks),
        "family_counts": dict(sorted(family_counts.items())),
        "holdout_provenance": {
            "source_lane": "layer4_hard_v0_3_0",
            "selection_rule": "split == holdout",
            "source_taskset_path": str(Path(source_taskset_path).resolve()) if Path(source_taskset_path).exists() else str(source_taskset_path),
        },
        "difficulty_profile": {
            "layer_4_case_count": len([row for row in holdout_annotations if str(row.get("difficulty_layer") or "") == "layer_4"]),
            "layer_4_share_pct": _ratio(
                len([row for row in holdout_annotations if str(row.get("difficulty_layer") or "") == "layer_4"]),
                len(holdout_annotations),
            ),
        },
        "coverage_delta": {
            "before_layer4_case_count": before_layer4,
            "after_layer4_case_count": after_layer4,
            "layer4_case_count_delta": after_layer4 - before_layer4,
        },
    }
    _write_json(out_root / "summary.json", payload)
    (out_root / "summary.md").write_text(
        "\n".join(
            [
                "# Agent Modelica Layer 4 Holdout v0.3.1",
                "",
                f"- status: `{payload.get('status')}`",
                f"- task_count: `{payload.get('task_count')}`",
                f"- family_counts: `{json.dumps(payload.get('family_counts') or {}, ensure_ascii=True)}`",
                f"- layer4_case_count_delta: `{payload['coverage_delta']['layer4_case_count_delta']}`",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the first harder Layer 4 holdout slice for v0.3.1")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--source-taskset", default=DEFAULT_SOURCE_TASKSET)
    parser.add_argument("--source-sidecar", default=DEFAULT_SOURCE_SIDECAR)
    parser.add_argument("--base-spec", default=DEFAULT_BASE_SPEC)
    parser.add_argument("--base-summary", default=DEFAULT_BASE_SUMMARY)
    args = parser.parse_args()
    payload = build_layer4_holdout_v0_3_1(
        out_dir=str(args.out_dir),
        source_taskset_path=str(args.source_taskset),
        source_sidecar_path=str(args.source_sidecar),
        base_spec_path=str(args.base_spec),
        base_summary_path=str(args.base_summary),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": int(payload.get("task_count") or 0)}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
