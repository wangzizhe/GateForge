from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_generation_workorder_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_generation_workorder_v0_3_3"
DEFAULT_PRIMARY_SLICE_SUMMARY = "artifacts/agent_modelica_track_c_primary_slice_v0_3_3/summary.json"
DEFAULT_V032_WORKORDER = "artifacts/agent_modelica_layer4_generation_workorder_v0_3_2/summary.json"


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


def _reason_hits(row: dict, gate_name: str, needle: str) -> bool:
    gate_reasons = row.get("gate_reasons") if isinstance(row.get("gate_reasons"), dict) else {}
    rows = gate_reasons.get(gate_name) if isinstance(gate_reasons.get(gate_name), list) else []
    return any(needle in str(x) for x in rows)


def _allocate_targets(rows: list[dict], freeze_ready_gap: int) -> list[dict]:
    remaining = max(0, int(freeze_ready_gap))
    weighted_rows: list[dict] = []
    for row in rows:
        base_weight = 3 if _norm(row.get("priority_bucket")) == "priority_1_generate_now" else 1
        weight = (
            base_weight
            + int(row.get("holdout_blocked_count") or 0)
            + int(row.get("attribution_blocked_count") or 0)
            + int(row.get("planner_blocked_count") or 0)
        )
        weighted_rows.append({**row, "_weight": max(1, weight)})
    total_weight = sum(int(row["_weight"]) for row in weighted_rows)
    if remaining <= 0 or total_weight <= 0:
        return [{k: v for k, v in row.items() if k != "_weight"} for row in weighted_rows]
    allocated = 0
    for idx, row in enumerate(weighted_rows):
        target = max(1, round((int(row["_weight"]) / total_weight) * remaining))
        if idx == len(weighted_rows) - 1:
            target = max(1, remaining - allocated)
        row["recommended_new_task_target_v0_3_3"] = int(target)
        allocated += int(target)
    return [{k: v for k, v in row.items() if k != "_weight"} for row in weighted_rows]


def build_generation_workorder(
    *,
    primary_slice_summary_path: str = DEFAULT_PRIMARY_SLICE_SUMMARY,
    v032_workorder_summary_path: str = DEFAULT_V032_WORKORDER,
) -> dict:
    primary = _load_json(primary_slice_summary_path)
    v032 = _load_json(v032_workorder_summary_path)
    excluded_rows = primary.get("excluded_rows") if isinstance(primary.get("excluded_rows"), list) else []
    v032_work_orders = v032.get("work_orders") if isinstance(v032.get("work_orders"), list) else []
    freeze_ready_gap = int((primary.get("metrics") or {}).get("freeze_ready_gap") or 0)

    family_rows: list[dict] = []
    for row in v032_work_orders:
        if not isinstance(row, dict):
            continue
        family_id = _norm(row.get("family_id"))
        family_excluded = [
            item
            for item in excluded_rows
            if isinstance(item, dict) and _norm(item.get("v0_3_family_id")) == family_id
        ]
        family_rows.append(
            {
                "family_id": family_id,
                "family_label": _norm(row.get("family_label") or family_id),
                "priority_bucket": _norm(row.get("priority_bucket")),
                "generator_module": _norm(row.get("generator_module")),
                "driver_script": _norm(row.get("driver_script")),
                "manifest_path": _norm(row.get("manifest_path")),
                "failure_types": [str(x) for x in (row.get("failure_types") or []) if _norm(x)],
                "command_hint": _norm(row.get("command_hint")),
                "execution_note": _norm(row.get("execution_note")),
                "holdout_blocked_count": len([item for item in family_excluded if not bool((item.get("gates") or {}).get("holdout_clean"))]),
                "attribution_blocked_count": len([item for item in family_excluded if not bool((item.get("gates") or {}).get("attribution"))]),
                "planner_blocked_count": len([item for item in family_excluded if not bool((item.get("gates") or {}).get("planner_sensitivity"))]),
                "layer4_observed_required": family_id == "initialization_singularity",
                "carryover_manifest_models": row.get("additional_manifest_models_not_yet_observed") if isinstance(row.get("additional_manifest_models_not_yet_observed"), list) else [],
            }
        )

    family_rows = _allocate_targets(family_rows, freeze_ready_gap)
    next_actions = [
        "Execute priority_1 families first using new mutation generation rather than reusing previously frozen packs.",
        "After new generation, rerun the v0.3.3 primary-slice builder before any external repeated-run expansion.",
        "Do not freeze newly generated cases until attribution-bearing reruns confirm planner sensitivity.",
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "READY_FOR_EXECUTION" if freeze_ready_gap > 0 else "NO_NEW_GENERATION_REQUIRED",
        "primary_slice_summary_path": str(Path(primary_slice_summary_path).resolve()) if Path(primary_slice_summary_path).exists() else str(primary_slice_summary_path),
        "v0_3_2_workorder_summary_path": str(Path(v032_workorder_summary_path).resolve()) if Path(v032_workorder_summary_path).exists() else str(v032_workorder_summary_path),
        "freeze_ready_gap": freeze_ready_gap,
        "work_orders": family_rows,
        "next_actions": next_actions,
    }


def _render_markdown(payload: dict) -> str:
    lines = [
        "# Track C Generation Workorder v0.3.3",
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
        lines.append(f"- recommended_new_task_target_v0_3_3: `{row.get('recommended_new_task_target_v0_3_3')}`")
        lines.append(f"- holdout_blocked_count: `{row.get('holdout_blocked_count')}`")
        lines.append(f"- attribution_blocked_count: `{row.get('attribution_blocked_count')}`")
        lines.append(f"- planner_blocked_count: `{row.get('planner_blocked_count')}`")
        lines.append(f"- driver_script: `{row.get('driver_script')}`")
        if _norm(row.get("manifest_path")):
            lines.append(f"- manifest_path: `{row.get('manifest_path')}`")
        lines.append(f"- command_hint: `{row.get('command_hint')}`")
        if bool(row.get("layer4_observed_required")):
            lines.append("- restriction: `Layer-4-observed members only`")
        lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    for idx, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {action}")
    lines.append("")
    return "\n".join(lines)


def run_generation_workorder(
    *,
    primary_slice_summary_path: str = DEFAULT_PRIMARY_SLICE_SUMMARY,
    v032_workorder_summary_path: str = DEFAULT_V032_WORKORDER,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = build_generation_workorder(
        primary_slice_summary_path=primary_slice_summary_path,
        v032_workorder_summary_path=v032_workorder_summary_path,
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", _render_markdown(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.3 holdout-clean generation workorder.")
    parser.add_argument("--primary-slice-summary", default=DEFAULT_PRIMARY_SLICE_SUMMARY)
    parser.add_argument("--v0-3-2-workorder-summary", default=DEFAULT_V032_WORKORDER)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = run_generation_workorder(
        primary_slice_summary_path=str(args.primary_slice_summary),
        v032_workorder_summary_path=str(args.v0_3_2_workorder_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "freeze_ready_gap": payload.get("freeze_ready_gap")}))


if __name__ == "__main__":
    main()
