from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_10_3_common import (
    DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR,
    DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR,
    READY_MAX_SINGLE_SOURCE_SHARE_PCT,
    READY_MIN_FAMILY_COUNT,
    READY_MIN_SOURCE_COUNT,
    READY_MIN_SUBSTRATE_SIZE,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_3_real_origin_substrate_builder import build_v103_real_origin_substrate_builder


def build_v103_real_origin_substrate_admission(
    *,
    real_origin_substrate_builder_path: str = str(DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    if not Path(real_origin_substrate_builder_path).exists():
        build_v103_real_origin_substrate_builder(out_dir=str(Path(real_origin_substrate_builder_path).parent))
    builder = load_json(real_origin_substrate_builder_path)
    rows = (
        builder.get("real_origin_substrate_candidate_table")
        if isinstance(builder.get("real_origin_substrate_candidate_table"), list)
        else []
    )
    evaluations = evaluate_candidate_rows(rows)
    size = len(rows)
    governance_clean = all(verdict.get("admitted") for verdict in evaluations) and len(evaluations) == size
    real_origin_only = all(verdict.get("source_origin_class") == "real_origin" for verdict in evaluations)
    no_proxy_rows = all(verdict.get("source_origin_class") != "workflow_proximal_proxy" for verdict in evaluations)
    provenance_explicit_ok = all(
        isinstance((row.get("real_origin_authenticity_audit") or {}).get("source_provenance"), str)
        and str((row.get("real_origin_authenticity_audit") or {}).get("source_provenance")).strip()
        for row in rows
    )
    source_mix = builder.get("source_mix") if isinstance(builder.get("source_mix"), dict) else {}
    workflow_family_mix = builder.get("workflow_family_mix") if isinstance(builder.get("workflow_family_mix"), dict) else {}
    complexity_mix = builder.get("complexity_mix") if isinstance(builder.get("complexity_mix"), dict) else {}
    max_single_source_share_pct = float(builder.get("max_single_source_share_pct") or 0.0)
    source_count = len([key for key, value in source_mix.items() if int(value) > 0])
    family_count = len([key for key, value in workflow_family_mix.items() if int(value) > 0])
    governance_pass_rate_pct = 100.0 * sum(1 for verdict in evaluations if verdict.get("admitted")) / size if size else 0.0

    ready_floor_met = (
        governance_clean
        and real_origin_only
        and no_proxy_rows
        and provenance_explicit_ok
        and size >= READY_MIN_SUBSTRATE_SIZE
        and source_count >= READY_MIN_SOURCE_COUNT
        and family_count >= READY_MIN_FAMILY_COUNT
        and max_single_source_share_pct <= READY_MAX_SINGLE_SOURCE_SHARE_PCT
    )
    partial_floor_met = governance_clean and real_origin_only and no_proxy_rows and provenance_explicit_ok and size > 0

    if ready_floor_met:
        admission_status = "ready"
    elif partial_floor_met:
        admission_status = "partial"
    else:
        admission_status = "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_real_origin_substrate_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission_status in {"ready", "partial"} else "FAIL",
        "real_origin_substrate_admission_status": admission_status,
        "real_origin_substrate_size": size,
        "governance_pass_rate_pct": governance_pass_rate_pct,
        "source_coverage_table": source_mix,
        "workflow_family_coverage_table": workflow_family_mix,
        "complexity_coverage_table": complexity_mix,
        "excluded_upstream_mainline_row_count": int(builder.get("excluded_upstream_mainline_row_count") or 0),
        "max_single_source_share_pct": max_single_source_share_pct,
        "source_count": source_count,
        "family_count": family_count,
        "governance_clean": governance_clean,
        "real_origin_only": real_origin_only,
        "no_proxy_rows": no_proxy_rows,
        "provenance_explicit_ok": provenance_explicit_ok,
        "ready_floor_met": ready_floor_met,
        "partial_floor_met": partial_floor_met,
        "candidate_row_evaluations": evaluations,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.3 Real-Origin Substrate Admission",
                "",
                f"- real_origin_substrate_admission_status: `{admission_status}`",
                f"- real_origin_substrate_size: `{size}`",
                f"- max_single_source_share_pct: `{max_single_source_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.3 real-origin substrate admission artifact.")
    parser.add_argument("--real-origin-substrate-builder", default=str(DEFAULT_REAL_ORIGIN_SUBSTRATE_BUILDER_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_REAL_ORIGIN_SUBSTRATE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v103_real_origin_substrate_admission(
        real_origin_substrate_builder_path=str(args.real_origin_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "real_origin_substrate_admission_status": payload.get("real_origin_substrate_admission_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
