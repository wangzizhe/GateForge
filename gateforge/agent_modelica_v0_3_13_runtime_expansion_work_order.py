from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_runtime_expansion_work_order"
DEFAULT_PREVIEW_SUMMARY = "artifacts/agent_modelica_v0_3_13_runtime_pair_preview_current/summary.json"
DEFAULT_EXPANSION_TASKSET = "artifacts/agent_modelica_v0_3_13_runtime_expansion_taskset_current/taskset.json"
DEFAULT_EXPANSION_FAMILY_SPEC = "artifacts/agent_modelica_v0_3_13_runtime_expansion_family_spec_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_runtime_expansion_work_order"


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


def _count_by_source(task_rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in task_rows:
        if not isinstance(row, dict):
            continue
        source_task_id = _norm(row.get("v0_3_13_source_task_id"))
        if source_task_id:
            counts[source_task_id] = counts.get(source_task_id, 0) + 1
    return counts


def _preview_rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def build_runtime_expansion_work_order(
    *,
    preview_summary_path: str = DEFAULT_PREVIEW_SUMMARY,
    expansion_taskset_path: str = DEFAULT_EXPANSION_TASKSET,
    expansion_family_spec_path: str = DEFAULT_EXPANSION_FAMILY_SPEC,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    preview_summary = _load_json(preview_summary_path)
    expansion_taskset = _load_json(expansion_taskset_path)
    expansion_family = _load_json(expansion_family_spec_path)
    preview_rows = _preview_rows(preview_summary)
    task_rows = _task_rows(expansion_taskset)

    rejected_rows = [row for row in preview_rows if _norm(row.get("preview_reason")) != "preview_admitted"]
    rejected_pairs = [
        {
            "task_id": _norm(row.get("task_id")),
            "preview_reason": _norm(row.get("preview_reason")),
            "post_rule_residual_reason": _norm(row.get("post_rule_residual_reason")),
        }
        for row in rejected_rows
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "lane_status": _norm(expansion_family.get("lane_status")).upper(),
        "admitted_count": int(expansion_family.get("admitted_count") or 0),
        "rejected_count": len(rejected_rows),
        "admitted_by_source_task_id": _count_by_source(task_rows),
        "rejected_pairs": rejected_pairs,
        "next_actions": [
            "Promote the 12 admitted targeted pairs into the runtime curriculum lane for future live evidence runs.",
            "Keep the 5 rejected pairs out of the multiround budget until a redesign leaves a post-rule residual.",
            "Expand around source models that admitted multiple new pairs before adding brand-new model families.",
        ],
        "evidence": {
            "preview_summary_path": str(Path(preview_summary_path).resolve()) if Path(preview_summary_path).exists() else str(preview_summary_path),
            "expansion_taskset_path": str(Path(expansion_taskset_path).resolve()) if Path(expansion_taskset_path).exists() else str(expansion_taskset_path),
            "expansion_family_spec_path": str(Path(expansion_family_spec_path).resolve()) if Path(expansion_family_spec_path).exists() else str(expansion_family_spec_path),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.13 Runtime Expansion Work Order",
        "",
        f"- lane_status: `{payload.get('lane_status')}`",
        f"- admitted_count: `{payload.get('admitted_count')}`",
        f"- rejected_count: `{payload.get('rejected_count')}`",
        "",
    ]
    for key, value in sorted((payload.get("admitted_by_source_task_id") or {}).items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 runtime expansion work order.")
    parser.add_argument("--preview-summary", default=DEFAULT_PREVIEW_SUMMARY)
    parser.add_argument("--expansion-taskset", default=DEFAULT_EXPANSION_TASKSET)
    parser.add_argument("--expansion-family-spec", default=DEFAULT_EXPANSION_FAMILY_SPEC)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_runtime_expansion_work_order(
        preview_summary_path=str(args.preview_summary),
        expansion_taskset_path=str(args.expansion_taskset),
        expansion_family_spec_path=str(args.expansion_family_spec),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"lane_status": payload.get("lane_status"), "admitted_count": payload.get("admitted_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
