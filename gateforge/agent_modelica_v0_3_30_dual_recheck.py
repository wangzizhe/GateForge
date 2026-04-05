from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_30_common import (
    DEFAULT_DISCOVERY_OUT_DIR,
    DEFAULT_DUAL_RECHECK_OUT_DIR,
    DEFAULT_DUAL_RECHECK_RESULTS_DIR,
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    DEFAULT_V0329_ENTRY_TASKSET_PATH,
    SCHEMA_PREFIX,
    apply_medium_redeclare_discovery_patch,
    fixture_dry_run_result,
    load_json,
    medium_redeclare_target_hit,
    now_utc,
    norm,
    parse_canonical_rhs_from_repair_step,
    rank_medium_rhs_candidates,
    run_dry_run,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_30_discovery_evidence import build_v0330_discovery_evidence
from .agent_modelica_v0_3_30_surface_index import build_v0330_surface_index


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dual_recheck"


def _dual_rows(payload: dict) -> list[dict]:
    rows = payload.get("dual_tasks")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _single_surface_by_source(payload: dict) -> dict[str, dict]:
    rows = payload.get("task_rows")
    by_source: dict[str, dict] = {}
    if not isinstance(rows, list):
        return by_source
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_id = norm(row.get("source_id"))
        if source_id and source_id not in by_source:
            by_source[source_id] = row
    return by_source


def _run_or_fixture(*, model_name: str, model_text: str, phase: str, use_fixture_only: bool) -> dict:
    if use_fixture_only:
        return fixture_dry_run_result(phase=phase)
    return run_dry_run(model_name, model_text)


def build_v0330_dual_recheck(
    *,
    discovery_path: str = str(DEFAULT_DISCOVERY_OUT_DIR / "summary.json"),
    surface_index_path: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"),
    entry_taskset_path: str = str(DEFAULT_V0329_ENTRY_TASKSET_PATH),
    results_dir: str = str(DEFAULT_DUAL_RECHECK_RESULTS_DIR),
    out_dir: str = str(DEFAULT_DUAL_RECHECK_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    del results_dir
    if not Path(discovery_path).exists():
        build_v0330_discovery_evidence(out_dir=str(Path(discovery_path).parent), use_fixture_only=use_fixture_only)
    if not Path(surface_index_path).exists():
        build_v0330_surface_index(out_dir=str(Path(surface_index_path).parent), use_fixture_only=use_fixture_only)
    discovery = load_json(discovery_path)
    if norm(discovery.get("execution_status")) != "executed":
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "SKIPPED",
            "execution_status": "not_executed_due_to_discovery_gate",
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_text(out_root / "summary.md", "# v0.3.30 Dual Recheck\n\n- status: `SKIPPED`\n")
        return summary

    taskset = load_json(entry_taskset_path)
    tasks = _dual_rows(taskset)
    surface_payload = load_json(surface_index_path)
    source_surface = _single_surface_by_source(surface_payload)
    rows: list[dict] = []
    for task in tasks:
        source_id = norm(task.get("source_id"))
        surface_row = source_surface.get(source_id) or {}
        repair_steps = list(task.get("repair_steps") or [])
        current_text = norm(task.get("mutated_model_text"))
        if not repair_steps:
            continue
        first_step = repair_steps[0]
        ranked_first = rank_medium_rhs_candidates(
            candidate_rhs_symbols=list(surface_row.get("candidate_rhs_symbols") or []),
            canonical_rhs_symbol=norm(surface_row.get("canonical_rhs_symbol")),
            canonical_package_path=norm(surface_row.get("canonical_package_path")),
            local_cluster_rhs_values=list(surface_row.get("local_cluster_rhs_values") or []),
            adjacent_component_package_paths=list(surface_row.get("adjacent_component_package_paths") or []),
        )
        first_selected = norm((ranked_first[0] or {}).get("candidate_rhs_symbol")) if ranked_first else ""
        first_repaired_text, first_patch = apply_medium_redeclare_discovery_patch(
            current_text=current_text,
            step=first_step,
            selected_rhs_symbol=first_selected,
        )
        if not first_patch.get("applied"):
            continue
        second_residual = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=first_repaired_text, phase="target_hit", use_fixture_only=use_fixture_only)
        retained = medium_redeclare_target_hit(second_residual)
        final_resolved = False
        if retained and len(repair_steps) >= 2:
            second_step = repair_steps[1]
            ranked_second = rank_medium_rhs_candidates(
                candidate_rhs_symbols=list(surface_row.get("candidate_rhs_symbols") or []),
                canonical_rhs_symbol=parse_canonical_rhs_from_repair_step(second_step),
                canonical_package_path=norm(surface_row.get("canonical_package_path")),
                local_cluster_rhs_values=list(surface_row.get("local_cluster_rhs_values") or []),
                adjacent_component_package_paths=list(surface_row.get("adjacent_component_package_paths") or []),
            )
            second_selected = norm((ranked_second[0] or {}).get("candidate_rhs_symbol")) if ranked_second else ""
            second_repaired_text, second_patch = apply_medium_redeclare_discovery_patch(
                current_text=first_repaired_text,
                step=second_step,
                selected_rhs_symbol=second_selected,
            )
            final_result = _run_or_fixture(model_name=norm(task.get("model_name")), model_text=second_repaired_text, phase="resolved", use_fixture_only=use_fixture_only) if second_patch.get("applied") else {}
            final_resolved = bool(final_result.get("check_model_pass"))
        rows.append(
            {
                "task_id": norm(task.get("task_id")),
                "second_residual_target_hit": retained,
                "second_residual_medium_redeclare_retained": retained,
                "dual_full_resolution": final_resolved,
            }
        )
    task_count = len(rows)
    second_count = sum(1 for row in rows if bool(row.get("second_residual_target_hit")))
    retained_count = sum(1 for row in rows if bool(row.get("second_residual_medium_redeclare_retained")))
    resolved_count = sum(1 for row in rows if bool(row.get("dual_full_resolution")))
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if rows else "EMPTY",
        "execution_status": "executed",
        "task_count": task_count,
        "post_first_fix_target_bucket_hit_rate_pct": round(100.0 * second_count / float(task_count), 1) if task_count else 0.0,
        "second_residual_medium_redeclare_retained_rate_pct": round(100.0 * retained_count / float(task_count), 1) if task_count else 0.0,
        "dual_full_resolution_rate_pct": round(100.0 * resolved_count / float(task_count), 1) if task_count else 0.0,
        "rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.30 Dual Recheck",
                "",
                f"- status: `{summary.get('status')}`",
                f"- post_first_fix_target_bucket_hit_rate_pct: `{summary.get('post_first_fix_target_bucket_hit_rate_pct')}`",
                f"- dual_full_resolution_rate_pct: `{summary.get('dual_full_resolution_rate_pct')}`",
            ]
        ),
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.30 dual recheck.")
    parser.add_argument("--discovery", default=str(DEFAULT_DISCOVERY_OUT_DIR / "summary.json"))
    parser.add_argument("--surface-index", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR / "surface_index.json"))
    parser.add_argument("--entry-taskset", default=str(DEFAULT_V0329_ENTRY_TASKSET_PATH))
    parser.add_argument("--results-dir", default=str(DEFAULT_DUAL_RECHECK_RESULTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_DUAL_RECHECK_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0330_dual_recheck(
        discovery_path=str(args.discovery),
        surface_index_path=str(args.surface_index),
        entry_taskset_path=str(args.entry_taskset),
        results_dir=str(args.results_dir),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps({"status": payload.get("status"), "execution_status": payload.get("execution_status"), "dual_full_resolution_rate_pct": payload.get("dual_full_resolution_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
