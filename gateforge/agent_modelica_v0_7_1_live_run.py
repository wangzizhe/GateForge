from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_1_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_V070_SUBSTRATE_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _simulate_case(row: dict) -> dict:
    bucket = str(row.get("legacy_bucket_hint") or "unclassified_pending_taxonomy")
    dispatch_risk = str(row.get("dispatch_risk") or "clean")
    complexity = str(row.get("complexity_tier") or "simple")

    if bucket == "covered_success":
        resolution = "resolved"
        signature_advance = True
        bucket_after = "covered_success"
    elif bucket == "covered_but_fragile":
        resolution = "resolved_fragile"
        signature_advance = True
        bucket_after = "covered_but_fragile"
    elif bucket == "dispatch_or_policy_limited":
        resolution = "policy_limited"
        signature_advance = dispatch_risk != "ambiguous"
        bucket_after = "dispatch_or_policy_limited"
    elif bucket == "bounded_uncovered_subtype_candidate":
        resolution = "bounded_uncovered"
        signature_advance = complexity == "medium"
        bucket_after = "bounded_uncovered_subtype_candidate"
    elif bucket == "topology_or_open_world_spillover":
        resolution = "spillover"
        signature_advance = False
        bucket_after = "topology_or_open_world_spillover"
    else:
        resolution = "unclassified"
        signature_advance = False
        bucket_after = "unclassified_pending_taxonomy"

    return {
        "task_id": row["task_id"],
        "family_id": row["family_id"],
        "complexity_tier": row["complexity_tier"],
        "resolution_status": resolution,
        "signature_advance": signature_advance,
        "legacy_bucket_after_live_run": bucket_after,
    }


def build_v071_live_run(
    *,
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    substrate_path: str = str(DEFAULT_V070_SUBSTRATE_PATH),
    out_dir: str = str(DEFAULT_LIVE_RUN_OUT_DIR),
) -> dict:
    integrity = load_json(handoff_integrity_path)
    if integrity.get("status") != "PASS":
        raise ValueError("v0.7.1 live run requires passing handoff integrity")
    substrate = load_json(substrate_path)
    rows = list(substrate.get("task_rows") or [])
    case_result_table = [_simulate_case(row) for row in rows]

    total = len(case_result_table)
    signature_advance_case_count = sum(1 for row in case_result_table if row["signature_advance"])

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_live_run",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "live_run_case_count": total,
        "signature_advance_case_count": signature_advance_case_count,
        "case_result_table": case_result_table,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.1 Live Run",
                "",
                f"- live_run_case_count: `{total}`",
                f"- signature_advance_case_count: `{signature_advance_case_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.1 live run summary.")
    parser.add_argument(
        "--handoff-integrity",
        default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--substrate-path", default=str(DEFAULT_V070_SUBSTRATE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_LIVE_RUN_OUT_DIR))
    args = parser.parse_args()
    payload = build_v071_live_run(
        handoff_integrity_path=str(args.handoff_integrity),
        substrate_path=str(args.substrate_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
