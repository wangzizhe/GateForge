from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_3_common import (
    DEFAULT_DECISION_ADJUDICATION_OUT_DIR,
    DEFAULT_DECISION_INPUT_TABLE_OUT_DIR,
    LEGACY_BUCKET_MAPPING_PARTIAL_MIN,
    LEGACY_BUCKET_MAPPING_READY_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_PARTIAL_MAX,
    SPILLOVER_READY_MAX,
    STABLE_COVERAGE_READY_MIN,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v073_decision_adjudication(
    *,
    decision_input_table_path: str = str(DEFAULT_DECISION_INPUT_TABLE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DECISION_ADJUDICATION_OUT_DIR),
) -> dict:
    table = load_json(decision_input_table_path)
    stable_coverage = float(table.get("stable_coverage_share_pct_stable") or 0.0)
    spillover = float(table.get("spillover_share_pct_stable") or 100.0)
    legacy_mapping = float(table.get("legacy_bucket_mapping_rate_pct_stable") or 0.0)
    complexity_pressure_profile = table.get("complexity_pressure_profile") or {}
    gap_summary = str(table.get("open_world_candidate_gap_summary") or "unknown")
    table_complete = bool(table.get("decision_input_table_complete"))

    if (
        not table_complete
        or legacy_mapping < LEGACY_BUCKET_MAPPING_PARTIAL_MIN
        or spillover > SPILLOVER_PARTIAL_MAX
        or not complexity_pressure_profile.get("explainable")
    ):
        status = "invalid"
    elif (
        table_complete
        and legacy_mapping >= LEGACY_BUCKET_MAPPING_READY_MIN
        and spillover <= SPILLOVER_READY_MAX
        and stable_coverage >= STABLE_COVERAGE_READY_MIN
        and gap_summary in {"supported_floor_met", "single_gap_complexity_complex_near_supported_floor"}
    ):
        status = "ready"
    else:
        status = "partial"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_decision_adjudication",
        "generated_at_utc": now_utc(),
        "status": "PASS" if status in {"ready", "partial"} else "FAIL",
        "decision_input_status": status,
        "stable_coverage_share_pct_stable": stable_coverage,
        "spillover_share_pct_stable": spillover,
        "legacy_bucket_mapping_rate_pct_stable": legacy_mapping,
        "complexity_pressure_profile": complexity_pressure_profile,
        "open_world_candidate_gap_summary": gap_summary,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.3 Decision Adjudication",
                "",
                f"- decision_input_status: `{status}`",
                f"- stable_coverage_share_pct_stable: `{stable_coverage}`",
                f"- spillover_share_pct_stable: `{spillover}`",
                f"- open_world_candidate_gap_summary: `{gap_summary}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.3 decision adjudication.")
    parser.add_argument("--decision-input-table", default=str(DEFAULT_DECISION_INPUT_TABLE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DECISION_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v073_decision_adjudication(
        decision_input_table_path=str(args.decision_input_table),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
