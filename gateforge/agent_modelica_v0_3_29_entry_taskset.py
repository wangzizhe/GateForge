from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_29_common import (
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_ENTRY_TASKSET_OUT_DIR,
    MEDIUM_ENTRY_DUAL_SPECS,
    MEDIUM_ENTRY_SINGLE_SPECS,
    MEDIUM_REDECLARE_TARGET_SUBTYPE,
    MEDIUM_SOURCE_SPECS,
    SCHEMA_PREFIX,
    apply_repair_step,
    build_mutated_text,
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
from .agent_modelica_v0_3_29_entry_family_spec import build_v0329_entry_family_spec


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_entry_taskset"


def _run_or_fixture(*, model_name: str, model_text: str, use_fixture_only: bool) -> dict:
    return fixture_medium_redeclare_result(passes=True) if use_fixture_only else run_dry_run(model_name, model_text)


def build_v0329_entry_taskset(
    *,
    entry_spec_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ENTRY_TASKSET_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(entry_spec_path).exists():
        build_v0329_entry_family_spec(out_dir=str(Path(entry_spec_path).parent))
    entry_spec = load_json(entry_spec_path)
    selected_family = norm(entry_spec.get("selected_family"))
    if selected_family != "medium_redeclare_alignment":
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "selected_family": selected_family,
            "entry_source_count": 0,
            "entry_single_task_count": 0,
            "entry_dual_sidecar_count": 0,
            "reason": "selected_family_not_supported_for_entry_taskset",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_json(out_root / "taskset.json", {"summary": summary, "sources": [], "single_tasks": [], "dual_tasks": []})
        return {"summary": summary, "sources": [], "single_tasks": [], "dual_tasks": []}

    single_rows: list[dict] = []
    dual_rows: list[dict] = []

    for spec in MEDIUM_ENTRY_SINGLE_SPECS:
        source = source_row_for(spec.get("source_id"))
        mutated_text, audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        dry_run = _run_or_fixture(model_name=norm(source.get("model_name")), model_text=mutated_text, use_fixture_only=use_fixture_only)
        if not medium_redeclare_target_hit(dry_run):
            continue
        single_rows.append(
            {
                "task_id": norm(spec.get("task_id")),
                "source_id": norm(spec.get("source_id")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "model_name": norm(source.get("model_name")),
                "source_model_text": norm(source.get("source_model_text")),
                "mutated_model_text": mutated_text,
                "patch_type": norm(spec.get("patch_type")),
                "allowed_patch_types": [norm(spec.get("patch_type"))],
                "repair_steps": list(spec.get("repair_steps") or []),
                "mutation_audit": audit,
                "first_failure_dry_run": dry_run,
            }
        )

    for spec in MEDIUM_ENTRY_DUAL_SPECS:
        source = source_row_for(spec.get("source_id"))
        mutated_text, audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        first_failure = _run_or_fixture(model_name=norm(source.get("model_name")), model_text=mutated_text, use_fixture_only=use_fixture_only)
        if not medium_redeclare_target_hit(first_failure):
            continue
        first_step = dict((spec.get("repair_steps") or [])[0] or {})
        repaired_text, apply_meta = apply_repair_step(mutated_text, first_step)
        second_residual = _run_or_fixture(model_name=norm(source.get("model_name")), model_text=repaired_text, use_fixture_only=use_fixture_only)
        if not apply_meta.get("applied") or not medium_redeclare_target_hit(second_residual):
            continue
        dual_rows.append(
            {
                "task_id": norm(spec.get("task_id")),
                "source_id": norm(spec.get("source_id")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "model_name": norm(source.get("model_name")),
                "source_model_text": norm(source.get("source_model_text")),
                "mutated_model_text": mutated_text,
                "repair_steps": list(spec.get("repair_steps") or []),
                "allowed_patch_types": sorted({norm(step.get("patch_type")) for step in (spec.get("repair_steps") or []) if norm(step.get("patch_type"))}),
                "mutation_audit": audit,
                "first_failure_dry_run": first_failure,
                "post_first_fix_apply": apply_meta,
                "post_first_fix_residual": second_residual,
            }
        )

    entry_source_ids = sorted({norm(row.get("source_id")) for row in single_rows + dual_rows if norm(row.get("source_id"))})
    entry_sources = [dict(row) for row in MEDIUM_SOURCE_SPECS if norm(row.get("source_id")) in entry_source_ids]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if len(entry_sources) >= 3 and len(single_rows) >= 6 and len(dual_rows) >= 4 else "FAIL",
        "selected_family": selected_family,
        "target_error_subtype": MEDIUM_REDECLARE_TARGET_SUBTYPE,
        "entry_source_count": len(entry_sources),
        "entry_single_task_count": len(single_rows),
        "entry_dual_sidecar_count": len(dual_rows),
        "allowed_patch_types": sorted(
            {
                norm(item)
                for row in single_rows + dual_rows
                for item in (row.get("allowed_patch_types") or [])
                if norm(item)
            }
        ),
        "post_first_fix_target_bucket_hit_rate_pct": round(
            100.0 * sum(1 for row in dual_rows if medium_redeclare_target_hit(row.get("post_first_fix_residual") or {})) / float(len(dual_rows)),
            1,
        )
        if dual_rows
        else 0.0,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "sources": entry_sources,
        "single_tasks": single_rows,
        "dual_tasks": dual_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "taskset.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.29 Entry Taskset",
                "",
                f"- status: `{summary.get('status')}`",
                f"- selected_family: `{summary.get('selected_family')}`",
                f"- entry_source_count: `{summary.get('entry_source_count')}`",
                f"- entry_single_task_count: `{summary.get('entry_single_task_count')}`",
                f"- entry_dual_sidecar_count: `{summary.get('entry_dual_sidecar_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.29 entry taskset.")
    parser.add_argument("--entry-spec", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ENTRY_TASKSET_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0329_entry_taskset(
        entry_spec_path=str(args.entry_spec),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps(payload.get("summary") or {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
