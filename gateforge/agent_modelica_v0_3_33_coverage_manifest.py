from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_33_common import (
    DEFAULT_MANIFEST_OUT_DIR,
    DEFAULT_V0331_CLOSEOUT_PATH,
    DEFAULT_V0332_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    ALLOWED_PATCH_TYPES,
    anti_noop_rejected,
    apply_repair_step,
    build_mutated_text,
    build_v0333_dual_specs,
    build_v0333_single_specs,
    coverage_target_hit,
    handoff_substrate_valid,
    load_json,
    norm,
    now_utc,
    probe_target_result,
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


def build_v0333_coverage_manifest(
    *,
    v0331_closeout_path: str = str(DEFAULT_V0331_CLOSEOUT_PATH),
    v0332_closeout_path: str = str(DEFAULT_V0332_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_MANIFEST_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    v0331 = load_json(v0331_closeout_path)
    v0332 = load_json(v0332_closeout_path)
    if not handoff_substrate_valid(v0331, v0332):
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "handoff_substrate_valid": False,
            "coverage_construction_mode": "handoff_substrate_invalid",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_json(out_root / "taskset.json", {"summary": summary, "single_tasks": [], "dual_tasks": []})
        return {"summary": summary, "single_tasks": [], "dual_tasks": []}

    singles: list[dict] = []
    rejected_singles: list[dict] = []
    for spec in build_v0333_single_specs():
        source = source_row_for(norm(spec.get("source_id")))
        mutated_text, mutation_audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        first_failure = probe_target_result(
            model_name=norm(spec.get("model_name")),
            model_text=mutated_text,
            wrong_symbol=norm(spec.get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        row = {
            **spec,
            "allowed_patch_types": list(ALLOWED_PATCH_TYPES),
            "source_model_text": norm(source.get("source_model_text")),
            "mutated_model_text": mutated_text,
            "mutation_audit": mutation_audit,
            "first_failure_dry_run": first_failure,
        }
        if coverage_target_hit(first_failure) and not anti_noop_rejected(first_failure):
            singles.append(row)
        else:
            rejected_singles.append(row)

    duals: list[dict] = []
    rejected_duals: list[dict] = []
    for spec in build_v0333_dual_specs():
        source = source_row_for(norm(spec.get("source_id")))
        mutated_text, mutation_audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        first_failure = probe_target_result(
            model_name=norm(spec.get("model_name")),
            model_text=mutated_text,
            wrong_symbol="MediumPipe",
            use_fixture_only=use_fixture_only,
        )
        first_step = ((spec.get("repair_steps") or [])[0] if isinstance(spec.get("repair_steps"), list) else {}) or {}
        patched_text, patch_meta = apply_repair_step(mutated_text, first_step)
        second_residual = probe_target_result(
            model_name=norm(spec.get("model_name")),
            model_text=patched_text,
            wrong_symbol="MediumPort",
            use_fixture_only=use_fixture_only,
        )
        row = {
            **spec,
            "allowed_patch_types": list(ALLOWED_PATCH_TYPES),
            "source_model_text": norm(source.get("source_model_text")),
            "mutated_model_text": mutated_text,
            "mutation_audit": mutation_audit,
            "first_failure_dry_run": first_failure,
            "post_first_fix_apply": patch_meta,
            "post_first_fix_residual": second_residual,
        }
        if coverage_target_hit(first_failure) and bool(patch_meta.get("applied")) and coverage_target_hit(second_residual):
            duals.append(row)
        else:
            rejected_duals.append(row)

    active_single = len(singles)
    active_dual = len(duals)
    if active_single >= 24 and active_dual >= 12:
        construction_mode = "promoted"
        status = "PASS"
    elif active_single >= 18 and active_dual >= 10:
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
        "source_count": len(sorted({norm(row.get("source_id")) for row in singles + duals if norm(row.get("source_id"))})),
        "active_single_task_count": active_single,
        "active_dual_task_count": active_dual,
        "single_context_counts": _count_by(singles, "pipe_slice_context"),
        "dual_context_counts": _count_by(duals, "pipe_slice_context"),
        "rejected_single_task_count": len(rejected_singles),
        "rejected_dual_task_count": len(rejected_duals),
        "post_first_fix_target_bucket_hit_rate_pct": round(
            100.0 * sum(1 for row in duals if coverage_target_hit(row.get("post_first_fix_residual") or {})) / float(active_dual),
            1,
        )
        if active_dual
        else 0.0,
    }
    payload = {
        "summary": summary,
        "single_tasks": singles,
        "dual_tasks": duals,
        "rejected_single_tasks": rejected_singles,
        "rejected_dual_tasks": rejected_duals,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "taskset.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.33 Coverage Manifest",
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
    parser = argparse.ArgumentParser(description="Build the v0.3.33 widened pipe-slice coverage manifest.")
    parser.add_argument("--v0331-closeout", default=str(DEFAULT_V0331_CLOSEOUT_PATH))
    parser.add_argument("--v0332-closeout", default=str(DEFAULT_V0332_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_MANIFEST_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0333_coverage_manifest(
        v0331_closeout_path=str(args.v0331_closeout),
        v0332_closeout_path=str(args.v0332_closeout),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    summary = payload.get("summary") or {}
    print(json.dumps({"status": summary.get("status"), "active_single_task_count": summary.get("active_single_task_count"), "active_dual_task_count": summary.get("active_dual_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
