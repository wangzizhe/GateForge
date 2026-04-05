from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_31_common import (
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_V0330_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    apply_repair_step,
    build_mutated_text,
    build_v0331_dual_specs,
    build_v0331_single_specs,
    build_v0331_source_specs,
    fixture_medium_redeclare_result,
    load_json,
    medium_redeclare_target_hit,
    norm,
    now_utc,
    run_dry_run,
    source_row_for,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_coverage_manifest"


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _run_or_fixture(*, model_name: str, model_text: str, use_fixture_only: bool) -> dict:
    return fixture_medium_redeclare_result(passes=True) if use_fixture_only else run_dry_run(model_name, model_text)


def build_v0331_coverage_manifest(
    *,
    v0330_closeout_path: str = str(DEFAULT_V0330_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MANIFEST_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    v0330 = load_json(v0330_closeout_path)
    v0330_decision = norm(((v0330.get("conclusion") or {}).get("version_decision")))
    handoff_substrate_valid = v0330_decision == "stage2_medium_redeclare_discovery_ready"
    if not handoff_substrate_valid:
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "handoff_substrate_valid": False,
            "coverage_construction_mode": "handoff_substrate_invalid",
            "reason": "v0330_closeout_not_discovery_ready",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_json(out_root / "taskset.json", {"summary": summary, "sources": [], "single_tasks": [], "dual_tasks": []})
        return {"summary": summary, "sources": [], "single_tasks": [], "dual_tasks": []}

    sources = build_v0331_source_specs()
    single_rows: list[dict] = []
    single_rejected_rows: list[dict] = []
    for spec in build_v0331_single_specs():
        source = source_row_for(norm(spec.get("source_id")))
        mutated_text, audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        first_failure = _run_or_fixture(model_name=norm(source.get("model_name")), model_text=mutated_text, use_fixture_only=use_fixture_only)
        row = {
            "task_id": norm(spec.get("task_id")),
            "source_id": norm(spec.get("source_id")),
            "complexity_tier": norm(spec.get("complexity_tier")),
            "component_name": norm(spec.get("component_name")),
            "component_subtype": norm(spec.get("component_subtype")),
            "patch_type": norm(spec.get("patch_type")),
            "allowed_patch_types": [norm(spec.get("patch_type"))],
            "model_name": norm(source.get("model_name")),
            "source_model_text": norm(source.get("source_model_text")),
            "mutated_model_text": mutated_text,
            "repair_steps": list(spec.get("repair_steps") or []),
            "mutation_audit": audit,
            "first_failure_dry_run": first_failure,
        }
        if medium_redeclare_target_hit(first_failure):
            single_rows.append(row)
        else:
            single_rejected_rows.append(row)

    dual_rows: list[dict] = []
    dual_rejected_rows: list[dict] = []
    for spec in build_v0331_dual_specs():
        source = source_row_for(norm(spec.get("source_id")))
        mutated_text, audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        first_failure = _run_or_fixture(model_name=norm(source.get("model_name")), model_text=mutated_text, use_fixture_only=use_fixture_only)
        row = {
            "task_id": norm(spec.get("task_id")),
            "source_id": norm(spec.get("source_id")),
            "complexity_tier": norm(spec.get("complexity_tier")),
            "component_name": norm(spec.get("component_name")),
            "component_subtype": norm(spec.get("component_subtype")),
            "model_name": norm(source.get("model_name")),
            "source_model_text": norm(source.get("source_model_text")),
            "mutated_model_text": mutated_text,
            "repair_steps": list(spec.get("repair_steps") or []),
            "allowed_patch_types": ["insert_redeclare_package_medium"],
            "mutation_audit": audit,
            "first_failure_dry_run": first_failure,
        }
        if not medium_redeclare_target_hit(first_failure):
            dual_rejected_rows.append(row)
            continue
        first_step = ((spec.get("repair_steps") or [])[0] if isinstance(spec.get("repair_steps"), list) else {}) or {}
        repaired_text, apply_meta = apply_repair_step(mutated_text, first_step)
        second_residual = _run_or_fixture(model_name=norm(source.get("model_name")), model_text=repaired_text, use_fixture_only=use_fixture_only)
        row["post_first_fix_apply"] = apply_meta
        row["post_first_fix_residual"] = second_residual
        if bool(apply_meta.get("applied")) and medium_redeclare_target_hit(second_residual):
            dual_rows.append(row)
        else:
            dual_rejected_rows.append(row)

    active_source_ids = sorted({norm(row.get("source_id")) for row in single_rows + dual_rows if norm(row.get("source_id"))})
    active_sources = [dict(row) for row in sources if norm(row.get("source_id")) in active_source_ids]
    active_single_count = len(single_rows)
    active_dual_count = len(dual_rows)
    if active_single_count >= 18 and active_dual_count >= 10:
        construction_mode = "promoted"
        status = "PASS"
    elif active_single_count >= 14 and active_dual_count >= 8:
        construction_mode = "degraded_but_executable"
        status = "PASS"
    else:
        construction_mode = "insufficient"
        status = "FAIL"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_substrate_valid": True,
        "coverage_construction_mode": construction_mode,
        "source_count": len(active_sources),
        "active_single_task_count": active_single_count,
        "active_dual_task_count": active_dual_count,
        "single_subtype_counts": _count_by(single_rows, "component_subtype"),
        "dual_subtype_counts": _count_by(dual_rows, "component_subtype"),
        "rejected_single_task_count": len(single_rejected_rows),
        "rejected_dual_task_count": len(dual_rejected_rows),
        "post_first_fix_target_bucket_hit_rate_pct": round(
            100.0
            * sum(1 for row in dual_rows if medium_redeclare_target_hit(row.get("post_first_fix_residual") or {}))
            / float(active_dual_count),
            1,
        )
        if active_dual_count
        else 0.0,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "sources": active_sources,
        "single_tasks": single_rows,
        "dual_tasks": dual_rows,
        "rejected_single_tasks": single_rejected_rows,
        "rejected_dual_tasks": dual_rejected_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "taskset.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.31 Coverage Manifest",
                "",
                f"- status: `{summary.get('status')}`",
                f"- coverage_construction_mode: `{summary.get('coverage_construction_mode')}`",
                f"- active_single_task_count: `{summary.get('active_single_task_count')}`",
                f"- active_dual_task_count: `{summary.get('active_dual_task_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.31 widened medium-redeclare coverage manifest.")
    parser.add_argument("--v0330-closeout", default=str(DEFAULT_V0330_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MANIFEST_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0331_coverage_manifest(
        v0330_closeout_path=str(args.v0330_closeout),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "active_single_task_count": summary.get("active_single_task_count"), "active_dual_task_count": summary.get("active_dual_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
