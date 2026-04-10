from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_10_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_10_0_common import (
    DEFAULT_DEPTH_PROBE_OUT_DIR,
    DEFAULT_GOVERNANCE_PACK_OUT_DIR,
    DEGRADED_MAINLINE_MIN_COUNT,
    DEGRADED_MAINLINE_MIN_FAMILY_COUNT,
    PROMOTED_MAINLINE_MIN_COUNT,
    PROMOTED_MAINLINE_MIN_FAMILY_COUNT,
    PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT,
    SCHEMA_PREFIX,
    SOURCE_ORIGIN_CLASSES,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_10_0_governance_pack import build_v1000_governance_pack


def build_v1000_depth_probe(
    *,
    governance_pack_path: str = str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DEPTH_PROBE_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    if not Path(governance_pack_path).exists():
        build_v1000_governance_pack(out_dir=str(Path(governance_pack_path).parent))
    governance = load_json(governance_pack_path)
    candidate_rows = governance.get("baseline_candidate_rows") if isinstance(governance.get("baseline_candidate_rows"), list) else []
    evaluations = evaluate_candidate_rows(candidate_rows)

    admitted_rows = [row for row in evaluations if row.get("admitted")]
    mainline_rows = [row for row in evaluations if row.get("mainline_counted")]
    mainline_count = len(mainline_rows)

    family_counter = Counter(str(row.get("family_id") or "") for row in mainline_rows if str(row.get("family_id") or ""))
    source_counter = Counter(str(row.get("source_id") or "") for row in mainline_rows if str(row.get("source_id") or ""))
    admitted_class_counter = Counter(
        str(row.get("source_origin_class") or "") for row in admitted_rows if str(row.get("source_origin_class") or "")
    )
    candidate_depth_by_source_origin_class = {
        origin_class: admitted_class_counter.get(origin_class, 0) for origin_class in SOURCE_ORIGIN_CLASSES
    }
    candidate_depth_by_workflow_family = dict(sorted(family_counter.items()))

    max_single_source_share_pct = 0.0
    if mainline_count:
        max_single_source_share_pct = round(max(source_counter.values()) * 100.0 / float(mainline_count), 1)

    promoted_floor_met = (
        mainline_count >= PROMOTED_MAINLINE_MIN_COUNT
        and len(family_counter) >= PROMOTED_MAINLINE_MIN_FAMILY_COUNT
        and max_single_source_share_pct <= PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT
    )
    degraded_floor_met = (
        mainline_count >= DEGRADED_MAINLINE_MIN_COUNT
        and len(family_counter) >= DEGRADED_MAINLINE_MIN_FAMILY_COUNT
        and candidate_depth_by_source_origin_class.get("workflow_proximal_proxy", 0) == 0
    )
    if mainline_count == 0:
        governance_status = "invalid"
    elif promoted_floor_met:
        governance_status = "governance_ready"
    elif degraded_floor_met:
        governance_status = "governance_partial"
    else:
        governance_status = "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_depth_probe",
        "generated_at_utc": now_utc(),
        "status": "PASS" if governance_status in {"governance_ready", "governance_partial"} else "FAIL",
        "real_origin_candidate_pool_total_count": len(candidate_rows),
        "admitted_candidate_count": len(admitted_rows),
        "mainline_real_origin_candidate_count": mainline_count,
        "candidate_depth_by_workflow_family": candidate_depth_by_workflow_family,
        "candidate_depth_by_source_origin_class": candidate_depth_by_source_origin_class,
        "max_single_source_share_pct": max_single_source_share_pct,
        "promoted_floor_met": promoted_floor_met,
        "degraded_floor_met": degraded_floor_met,
        "needs_additional_real_origin_sources": governance_status != "governance_ready",
        "real_origin_candidate_governance_status": governance_status,
        "candidate_row_evaluations": evaluations,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.0 Depth Probe",
                "",
                f"- real_origin_candidate_governance_status: `{governance_status}`",
                f"- mainline_real_origin_candidate_count: `{mainline_count}`",
                f"- candidate_depth_by_workflow_family: `{candidate_depth_by_workflow_family}`",
                f"- max_single_source_share_pct: `{max_single_source_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.0 real-origin candidate-pool depth probe artifact.")
    parser.add_argument("--governance-pack", default=str(DEFAULT_GOVERNANCE_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DEPTH_PROBE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v1000_depth_probe(governance_pack_path=str(args.governance_pack), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "real_origin_candidate_governance_status": payload.get("real_origin_candidate_governance_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
