from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_32_common import (
    DEFAULT_TRIAGE_OUT_DIR,
    DEFAULT_V0331_CLOSEOUT_PATH,
    PIPE_PATTERN_SPECS,
    SCHEMA_PREFIX,
    anti_noop_rejected,
    apply_repair_step,
    build_pipe_dual_spec,
    build_pipe_single_spec,
    build_mutated_text,
    bounded_medium_target_family,
    handoff_substrate_valid,
    load_json,
    norm,
    now_utc,
    pipe_slice_target_hit,
    pipe_target_signature,
    probe_target_result,
    source_row_for,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_pipe_viability_triage"


def build_v0332_pipe_viability_triage(
    *,
    v0331_closeout_path: str = str(DEFAULT_V0331_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_TRIAGE_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    v0331 = load_json(v0331_closeout_path)
    if not handoff_substrate_valid(v0331):
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": now_utc(),
            "status": "FAIL",
            "handoff_substrate_valid": False,
            "version_decision": "handoff_substrate_invalid",
            "accepted_pattern_count": 0,
            "selected_pipe_patterns": [],
        }
        out_root = Path(out_dir)
        write_json(out_root / "summary.json", summary)
        write_json(out_root / "records.json", {"summary": summary, "pattern_rows": []})
        return {"summary": summary, "pattern_rows": []}

    rows: list[dict] = []
    accepted_patterns: list[str] = []
    for spec in PIPE_PATTERN_SPECS:
        single_spec = build_pipe_single_spec(norm(spec.get("source_id")), norm(spec.get("component_name")))
        source = source_row_for(norm(single_spec.get("source_id")))
        mutated_text, mutation_audit = build_mutated_text(
            norm(source.get("source_model_text")),
            list(single_spec.get("injection_replacements") or []),
        )
        first_failure = probe_target_result(
            model_name=norm(source.get("model_name")),
            model_text=mutated_text,
            wrong_symbol=norm(single_spec.get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        dual_first, dual_second = tuple(spec.get("dual_precheck_components") or ("", ""))
        dual_spec = build_pipe_dual_spec(norm(spec.get("source_id")), norm(dual_first), norm(dual_second))
        dual_mutated_text, dual_mutation_audit = build_mutated_text(
            norm(source.get("source_model_text")),
            list(dual_spec.get("injection_replacements") or []),
        )
        dual_first_failure = probe_target_result(
            model_name=norm(source.get("model_name")),
            model_text=dual_mutated_text,
            wrong_symbol=norm(build_pipe_single_spec(norm(spec.get("source_id")), norm(dual_first)).get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        first_step = ((dual_spec.get("repair_steps") or [])[0] if isinstance(dual_spec.get("repair_steps"), list) else {}) or {}
        post_first_text, post_first_apply = apply_repair_step(dual_mutated_text, first_step)
        post_first_residual = probe_target_result(
            model_name=norm(source.get("model_name")),
            model_text=post_first_text,
            wrong_symbol=norm(build_pipe_single_spec(norm(spec.get("source_id")), norm(dual_second)).get("wrong_symbol")),
            use_fixture_only=use_fixture_only,
        )
        first_target = pipe_slice_target_hit(first_failure)
        dual_first_target = pipe_slice_target_hit(dual_first_failure)
        second_target = pipe_slice_target_hit(post_first_residual)
        anti_noop = not anti_noop_rejected(first_failure)
        accepted = bool(first_target and dual_first_target and anti_noop and bool(post_first_apply.get("applied")) and second_target)
        if accepted:
            accepted_patterns.append(norm(spec.get("pattern_id")))
        rows.append(
            {
                "pattern_id": norm(spec.get("pattern_id")),
                "source_id": norm(spec.get("source_id")),
                "component_name": norm(spec.get("component_name")),
                "dual_precheck_components": [norm(dual_first), norm(dual_second)],
                "mutation_audit": mutation_audit,
                "dual_mutation_audit": dual_mutation_audit,
                "first_failure": first_failure,
                "first_failure_signature": pipe_target_signature(first_failure),
                "first_failure_target_family": bounded_medium_target_family(first_failure),
                "anti_noop_pass": anti_noop,
                "dual_first_failure": dual_first_failure,
                "dual_first_target_hit": dual_first_target,
                "post_first_fix_apply": post_first_apply,
                "post_first_fix_residual": post_first_residual,
                "post_first_fix_target_hit": second_target,
                "accepted_for_pipe_slice_entry": accepted,
            }
        )

    accepted_count = len(accepted_patterns)
    if accepted_count >= 2:
        status = "PASS"
        version_decision = "pipe_slice_triage_ready"
    else:
        status = "FAIL"
        version_decision = "stage2_medium_redeclare_pipe_slice_boundary_rejected"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_substrate_valid": True,
        "accepted_pattern_count": accepted_count,
        "selected_pipe_patterns": accepted_patterns,
        "version_decision": version_decision,
        "target_bucket": "stage_2_structural_balance_reference|undefined_symbol_or_equivalent_bounded_medium_target",
    }
    payload = {
        "summary": summary,
        "pattern_rows": rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "records.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.32 Pipe Viability Triage",
                "",
                f"- status: `{summary.get('status')}`",
                f"- accepted_pattern_count: `{summary.get('accepted_pattern_count')}`",
                f"- selected_pipe_patterns: `{', '.join(summary.get('selected_pipe_patterns') or [])}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v0.3.32 pipe-slice viability triage.")
    parser.add_argument("--v0331-closeout", default=str(DEFAULT_V0331_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_TRIAGE_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0332_pipe_viability_triage(
        v0331_closeout_path=str(args.v0331_closeout),
        out_dir=str(args.out_dir),
        use_fixture_only=bool(args.use_fixture_only),
    )
    print(json.dumps(payload.get("summary") or {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
