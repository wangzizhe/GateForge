from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_29_common import (
    DEFAULT_TRIAGE_OUT_DIR,
    LOCAL_CONNECTION_PATTERN_SPECS,
    MEDIUM_FALLBACK_PATTERN_SPECS,
    SCHEMA_PREFIX,
    build_mutated_text,
    fixture_local_connection_result,
    fixture_medium_redeclare_result,
    local_connection_target_hit,
    medium_redeclare_target_hit,
    norm,
    now_utc,
    run_dry_run,
    source_row_for,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_viability_triage"


def _local_connection_rows(*, use_fixture_only: bool) -> list[dict]:
    rows: list[dict] = []
    for index, spec in enumerate(LOCAL_CONNECTION_PATTERN_SPECS):
        source = source_row_for(spec.get("source_id"))
        mutated_text, audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        dry_run = (
            fixture_local_connection_result(passes=(index == 0))
            if use_fixture_only
            else run_dry_run(norm(source.get("model_name")), mutated_text)
        )
        target_bucket_hit = local_connection_target_hit(dry_run)
        accepted = bool(target_bucket_hit) and not bool(spec.get("topology_intent_heavy"))
        rows.append(
            {
                "pattern_id": norm(spec.get("pattern_id")),
                "source_id": norm(spec.get("source_id")),
                "model_name": norm(source.get("model_name")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "mutation_kind": norm(spec.get("mutation_kind")),
                "allowed_patch_types": list(spec.get("allowed_patch_types") or []),
                "topology_intent_heavy": bool(spec.get("topology_intent_heavy")),
                "mutation_audit": audit,
                "dry_run": dry_run,
                "target_bucket_hit": bool(target_bucket_hit),
                "accepted_for_entry_family": bool(accepted),
            }
        )
    return rows


def _fallback_rows(*, use_fixture_only: bool) -> list[dict]:
    rows: list[dict] = []
    for spec in MEDIUM_FALLBACK_PATTERN_SPECS:
        source = source_row_for(spec.get("source_id"))
        mutated_text, audit = build_mutated_text(norm(source.get("source_model_text")), list(spec.get("injection_replacements") or []))
        dry_run = fixture_medium_redeclare_result(passes=True) if use_fixture_only else run_dry_run(norm(source.get("model_name")), mutated_text)
        rows.append(
            {
                "pattern_id": norm(spec.get("pattern_id")),
                "source_id": norm(spec.get("source_id")),
                "model_name": norm(source.get("model_name")),
                "complexity_tier": norm(spec.get("complexity_tier")),
                "patch_type": norm(spec.get("patch_type")),
                "mutation_kind": norm(spec.get("mutation_kind")),
                "allowed_patch_types": [norm(spec.get("patch_type"))],
                "mutation_audit": audit,
                "dry_run": dry_run,
                "target_bucket_hit": bool(medium_redeclare_target_hit(dry_run)),
            }
        )
    return rows


def build_v0329_viability_triage(*, out_dir: str = str(DEFAULT_TRIAGE_OUT_DIR), use_fixture_only: bool = False) -> dict:
    local_rows = _local_connection_rows(use_fixture_only=use_fixture_only)
    local_pass_count = sum(1 for row in local_rows if row.get("accepted_for_entry_family"))
    if local_pass_count >= 2:
        selected_family = "local_connection_fix"
        fallback_rows: list[dict] = []
        fallback_triggered = False
    else:
        selected_family = ""
        fallback_rows = _fallback_rows(use_fixture_only=use_fixture_only)
        fallback_triggered = True
        if sum(1 for row in fallback_rows if row.get("target_bucket_hit")) >= 1:
            selected_family = "medium_redeclare_alignment"

    if selected_family == "local_connection_fix":
        status = "PASS"
        version_decision = "stage2_third_family_entry_partially_ready"
    elif selected_family == "medium_redeclare_alignment":
        status = "PASS"
        version_decision = "stage2_third_family_entry_ready"
    else:
        status = "FAIL"
        version_decision = "stage2_third_family_boundary_rejected"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "local_connection_pattern_count": len(local_rows),
        "local_connection_accepted_pattern_count": local_pass_count,
        "local_connection_threshold_met": local_pass_count >= 2,
        "fallback_triggered": bool(fallback_triggered),
        "fallback_pattern_count": len(fallback_rows),
        "fallback_target_bucket_hit_count": sum(1 for row in fallback_rows if row.get("target_bucket_hit")),
        "selected_family": selected_family,
        "version_decision": version_decision,
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "local_connection_patterns": local_rows,
        "fallback_patterns": fallback_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "records.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.29 Viability Triage",
                "",
                f"- status: `{summary.get('status')}`",
                f"- local_connection_accepted_pattern_count: `{summary.get('local_connection_accepted_pattern_count')}`",
                f"- fallback_triggered: `{summary.get('fallback_triggered')}`",
                f"- selected_family: `{summary.get('selected_family')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.3.29 third-family viability triage.")
    parser.add_argument("--out-dir", default=str(DEFAULT_TRIAGE_OUT_DIR))
    parser.add_argument("--use-fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0329_viability_triage(out_dir=str(args.out_dir), use_fixture_only=bool(args.use_fixture_only))
    print(json.dumps(payload.get("summary") or {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
