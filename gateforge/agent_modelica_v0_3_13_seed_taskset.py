from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_seed_taskset"
DEFAULT_AUDIT_SUMMARY = "artifacts/agent_modelica_v0_3_13_v0_3_5_audit_current/summary.json"
DEFAULT_PREVIEW_SUMMARY = "artifacts/agent_modelica_v0_3_13_trajectory_preview_v0_3_5_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_seed_taskset"
COURSE_STAGE = "two_step_residual"
SEED_SOURCE = "v0_3_5_audited_seed"
FAMILY_RUNTIME = "surface_cleanup_then_runtime_parameter_recovery"
FAMILY_INITIALIZATION = "surface_cleanup_then_initialization_parameter_recovery"
SUPPORTED_FAMILIES = {FAMILY_RUNTIME, FAMILY_INITIALIZATION}


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


def _load_preview_rows(path: str | Path) -> dict[str, dict]:
    payload = _load_json(path)
    rows = payload.get("rows")
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


def _seed_family_from_audit_row(row: dict) -> str:
    cluster_id = _norm(row.get("residual_signal_cluster_id"))
    if cluster_id == "runtime_parameter_recovery":
        return FAMILY_RUNTIME
    if cluster_id == "initialization_parameter_recovery":
        return FAMILY_INITIALIZATION
    return ""


def _family_design_contract(family_id: str) -> dict:
    if family_id == FAMILY_RUNTIME:
        return {
            "family_goal": "surface_cleanup_then_runtime_parameter_recovery",
            "round_1_expectation": "deterministic marker cleanup removes the synthetic top layer",
            "round_2_expectation": "runtime residual remains and should point the agent at a parameter direction",
            "round_3_expectation": "parameter recovery resolves the residual without requiring new branch policy",
        }
    if family_id == FAMILY_INITIALIZATION:
        return {
            "family_goal": "surface_cleanup_then_initialization_parameter_recovery",
            "round_1_expectation": "deterministic marker cleanup removes the synthetic top layer",
            "round_2_expectation": "initialization residual becomes visible after cleanup",
            "round_3_expectation": "parameter recovery resolves the residual without needing a new branch-choice mechanism",
        }
    return {}


def build_seed_row(*, audit_row: dict, preview_row: dict) -> dict | None:
    family_id = _seed_family_from_audit_row(audit_row)
    if family_id not in SUPPORTED_FAMILIES:
        return None
    if not bool(audit_row.get("preview_admission")):
        return None
    if _norm(audit_row.get("success_pattern")) != "rule_then_llm_multiround_success":
        return None
    return {
        "task_id": _norm(audit_row.get("task_id")),
        "v0_3_13_family_id": family_id,
        "course_stage": COURSE_STAGE,
        "seed_source": SEED_SOURCE,
        "hidden_base_operator": _norm(audit_row.get("hidden_base_operator")),
        "masking_pattern": _norm(audit_row.get("masking_pattern")),
        "surface_rule_id": _norm(audit_row.get("surface_rule_id")),
        "surface_rule_reason": _norm(audit_row.get("surface_rule_reason")),
        "residual_signal_cluster_id": _norm(audit_row.get("residual_signal_cluster_id")),
        "first_attempt_stage_subtype": _norm(audit_row.get("first_attempt_stage_subtype")),
        "second_attempt_stage_subtype": _norm(audit_row.get("second_attempt_stage_subtype")),
        "llm_plan_candidate_parameters": list(audit_row.get("llm_plan_candidate_parameters") or []),
        "resolution_path": _norm(audit_row.get("resolution_path")),
        "rounds_used": int(audit_row.get("rounds_used") or 0),
        "preview_contract": {
            "surface_fixable_by_rule": bool(preview_row.get("surface_fixable_by_rule")),
            "surface_rule_id": _norm(preview_row.get("surface_rule_id")),
            "post_rule_residual_stage": _norm(preview_row.get("post_rule_residual_stage")),
            "post_rule_residual_error_type": _norm(preview_row.get("post_rule_residual_error_type")),
            "post_rule_residual_reason": _norm(preview_row.get("post_rule_residual_reason")),
            "preview_admission": bool(preview_row.get("preview_admission")),
        },
        "design_contract": _family_design_contract(family_id),
    }


def _family_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        family_id = _norm(row.get("v0_3_13_family_id"))
        if not family_id:
            continue
        counts[family_id] = counts.get(family_id, 0) + 1
    return counts


def build_v0_3_13_seed_taskset(
    *,
    audit_summary_path: str = DEFAULT_AUDIT_SUMMARY,
    preview_summary_path: str = DEFAULT_PREVIEW_SUMMARY,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    audit_payload = _load_json(audit_summary_path)
    audit_rows = audit_payload.get("rows")
    audit_rows = [row for row in audit_rows if isinstance(row, dict)] if isinstance(audit_rows, list) else []
    preview_rows = _load_preview_rows(preview_summary_path)
    converted = []
    for row in audit_rows:
        task_id = _norm(row.get("task_id"))
        converted_row = build_seed_row(audit_row=row, preview_row=preview_rows.get(task_id, {}))
        if converted_row is not None:
            converted.append(converted_row)

    out_root = Path(out_dir)
    for row in converted:
        _write_json(out_root / "tasks" / f"{row['task_id']}.json", row)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if converted else "EMPTY",
        "audit_summary_path": str(Path(audit_summary_path).resolve()) if Path(audit_summary_path).exists() else str(audit_summary_path),
        "preview_summary_path": str(Path(preview_summary_path).resolve()) if Path(preview_summary_path).exists() else str(preview_summary_path),
        "course_stage": COURSE_STAGE,
        "task_count": len(converted),
        "family_counts": _family_counts(converted),
        "task_ids": [row["task_id"] for row in converted],
        "tasks": converted,
    }
    _write_json(out_root / "taskset.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.13 Seed Taskset",
                "",
                f"- status: `{payload.get('status')}`",
                f"- course_stage: `{payload.get('course_stage')}`",
                f"- task_count: `{payload.get('task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 synthetic seed taskset from the audited v0.3.5 seeds.")
    parser.add_argument("--audit-summary", default=DEFAULT_AUDIT_SUMMARY)
    parser.add_argument("--preview-summary", default=DEFAULT_PREVIEW_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_13_seed_taskset(
        audit_summary_path=str(args.audit_summary),
        preview_summary_path=str(args.preview_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
