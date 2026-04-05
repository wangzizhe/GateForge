from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .agent_modelica_v0_3_32_common import (
    ALLOWED_PATCH_TYPES,
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_TRIAGE_OUT_DIR,
    SCHEMA_PREFIX,
    anti_noop_rejected,
    apply_repair_step,
    build_mutated_text,
    build_v0332_dual_specs,
    build_v0332_single_specs,
    norm,
    now_utc,
    pipe_slice_target_hit,
    probe_target_result,
    source_row_for,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_32_pipe_viability_triage import build_v0332_pipe_viability_triage
from .agent_modelica_v0_3_30_common import parse_canonical_rhs_from_repair_step


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_entry_spec"


def build_v0332_entry_spec(
    *,
    triage_path: str = str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    if not Path(triage_path).exists():
        build_v0332_pipe_viability_triage(out_dir=str(Path(triage_path).parent), use_fixture_only=use_fixture_only)
    triage = json.loads(Path(triage_path).read_text(encoding="utf-8"))
    selected_patterns = {norm(x) for x in (triage.get("selected_pipe_patterns") or [])}
    handoff_valid = bool(triage.get("handoff_substrate_valid"))
    if not handoff_valid or len(selected_patterns) < 2:
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "entry_status": "boundary_rejected",
            "selected_pipe_patterns": sorted(selected_patterns),
            "active_single_task_count": 0,
            "active_dual_sidecar_count": 0,
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_json(out_root / "taskset.json", {"summary": summary, "single_tasks": [], "dual_tasks": []})
        return {"summary": summary, "single_tasks": [], "dual_tasks": []}

    singles: list[dict] = []
    rejected_singles: list[dict] = []
    for spec in build_v0332_single_specs():
        if norm(spec.get("pattern_id")) not in selected_patterns:
            continue
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
            "source_model_text": norm(source.get("source_model_text")),
            "mutated_model_text": mutated_text,
            "mutation_audit": mutation_audit,
            "first_failure_dry_run": first_failure,
            "canonical_rhs_symbol": parse_canonical_rhs_from_repair_step(((spec.get("repair_steps") or [])[0] if isinstance(spec.get("repair_steps"), list) else {}) or {}),
        }
        if pipe_slice_target_hit(first_failure) and not anti_noop_rejected(first_failure):
            singles.append(row)
        else:
            rejected_singles.append(row)

    duals: list[dict] = []
    rejected_duals: list[dict] = []
    for spec in build_v0332_dual_specs():
        source = source_row_for(norm(spec.get("source_id")))
        mutated_text, mutation_audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        first_step = ((spec.get("repair_steps") or [])[0] if isinstance(spec.get("repair_steps"), list) else {}) or {}
        second_step = ((spec.get("repair_steps") or [None, {}])[1] if isinstance(spec.get("repair_steps"), list) and len(spec.get("repair_steps") or []) > 1 else {}) or {}
        wrong_symbol = re.search(r"redeclare package Medium = ([A-Za-z_][A-Za-z0-9_]*)", norm(first_step.get("match_text")) or "")
        first_failure = probe_target_result(
            model_name=norm(spec.get("model_name")),
            model_text=mutated_text,
            wrong_symbol=norm(wrong_symbol.group(1) if wrong_symbol else "MediumPipe"),
            use_fixture_only=use_fixture_only,
        )
        patched_text, patch_meta = apply_repair_step(mutated_text, first_step)
        wrong_symbol_2 = re.search(r"redeclare package Medium = ([A-Za-z_][A-Za-z0-9_]*)", norm(second_step.get("match_text")) or "")
        second_residual = probe_target_result(
            model_name=norm(spec.get("model_name")),
            model_text=patched_text,
            wrong_symbol=norm(wrong_symbol_2.group(1) if wrong_symbol_2 else "MediumPort"),
            use_fixture_only=use_fixture_only,
        )
        row = {
            **spec,
            "source_model_text": norm(source.get("source_model_text")),
            "mutated_model_text": mutated_text,
            "mutation_audit": mutation_audit,
            "first_failure_dry_run": first_failure,
            "post_first_fix_apply": patch_meta,
            "post_first_fix_residual": second_residual,
        }
        if pipe_slice_target_hit(first_failure) and bool(patch_meta.get("applied")) and pipe_slice_target_hit(second_residual):
            duals.append(row)
        else:
            rejected_duals.append(row)

    status = "PASS" if len(singles) >= 4 and len(duals) >= 3 else "FAIL"
    entry_status = "entry_frozen" if status == "PASS" else "boundary_rejected"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "entry_status": entry_status,
        "selected_pipe_patterns": sorted(selected_patterns),
        "entry_source_count": len(sorted({norm(row.get("source_id")) for row in singles + duals if norm(row.get("source_id"))})),
        "active_single_task_count": len(singles),
        "active_dual_sidecar_count": len(duals),
        "allowed_patch_types": list(ALLOWED_PATCH_TYPES),
        "allowed_patch_scope": "single_component_redeclare_clause_only",
        "max_patch_count_per_round": 1,
        "rejected_single_task_count": len(rejected_singles),
        "rejected_dual_task_count": len(rejected_duals),
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
                "# v0.3.32 Pipe Entry Spec",
                "",
                f"- status: `{summary.get('status')}`",
                f"- active_single_task_count: `{summary.get('active_single_task_count')}`",
                f"- active_dual_sidecar_count: `{summary.get('active_dual_sidecar_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the v0.3.32 pipe-like entry spec.")
    parser.add_argument("--triage", default=str(DEFAULT_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0332_entry_spec(
        triage_path=str(args.triage),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps(payload.get("summary") or {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
