from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .agent_modelica_v0_10_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_10_1_candidate_source_admission import build_v101_candidate_source_admission
from .agent_modelica_v0_10_1_common import (
    DEFAULT_POOL_DELTA_OUT_DIR,
    DEFAULT_SOURCE_ADMISSION_OUT_DIR,
    DEFAULT_V1000_CLOSEOUT_PATH,
    DEFAULT_V1000_GOVERNANCE_PACK_PATH,
    DEGRADED_MAINLINE_MIN_COUNT,
    DEGRADED_MAINLINE_MIN_FAMILY_COUNT,
    MIN_NEW_REAL_SOURCE_MAINLINE_YIELD,
    PROMOTED_MAINLINE_MIN_COUNT,
    PROMOTED_MAINLINE_MIN_FAMILY_COUNT,
    PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def _max_source_share_pct(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    source_counter = Counter(str(row.get("source_id") or "") for row in rows if str(row.get("source_id") or ""))
    if not source_counter:
        return 0.0
    return round(max(source_counter.values()) * 100.0 / float(len(rows)), 1)


def build_v101_pool_delta_and_diversity_report(
    *,
    v1000_closeout_path: str = str(DEFAULT_V1000_CLOSEOUT_PATH),
    v1000_governance_pack_path: str = str(DEFAULT_V1000_GOVERNANCE_PACK_PATH),
    source_admission_path: str = str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_POOL_DELTA_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    if not Path(source_admission_path).exists():
        build_v101_candidate_source_admission(out_dir=str(Path(source_admission_path).parent))

    upstream_closeout = load_json(v1000_closeout_path)
    upstream_conclusion = upstream_closeout.get("conclusion") if isinstance(upstream_closeout.get("conclusion"), dict) else {}
    upstream_depth_probe = upstream_closeout.get("depth_probe") if isinstance(upstream_closeout.get("depth_probe"), dict) else {}
    upstream_governance = load_json(v1000_governance_pack_path)
    source_admission = load_json(source_admission_path)

    baseline_rows = (
        upstream_governance.get("baseline_candidate_rows")
        if isinstance(upstream_governance.get("baseline_candidate_rows"), list)
        else []
    )
    intake = (
        source_admission.get("candidate_source_intake_table")
        if isinstance(source_admission.get("candidate_source_intake_table"), list)
        else []
    )
    admitted_sources = [row for row in intake if isinstance(row, dict) and row.get("source_admission_pass")]

    new_candidate_rows: list[dict] = []
    new_source_mainline_contribution_table: list[dict] = []
    for source in admitted_sources:
        rows = source.get("candidate_rows") if isinstance(source.get("candidate_rows"), list) else []
        new_candidate_rows.extend(rows)
        new_source_mainline_contribution_table.append(
            {
                "source_id": source["source_id"],
                "source_origin_class": source["source_origin_class"],
                "governance_passing_candidate_count": source["governance_passing_candidate_count"],
                "mainline_real_origin_candidate_count": source["mainline_real_origin_candidate_count"],
            }
        )

    combined_rows = list(baseline_rows) + list(new_candidate_rows)
    combined_evaluations = evaluate_candidate_rows(combined_rows)
    admitted_combined = [row for row, verdict in zip(combined_rows, combined_evaluations) if verdict.get("admitted")]
    mainline_combined = [row for row, verdict in zip(combined_rows, combined_evaluations) if verdict.get("mainline_counted")]

    family_counter = Counter(str(row.get("family_id") or "") for row in mainline_combined if str(row.get("family_id") or ""))
    class_counter = Counter(
        str((row.get("real_origin_authenticity_audit") or {}).get("source_origin_class") or "")
        for row in admitted_combined
        if isinstance(row, dict)
    )
    candidate_depth_by_workflow_family = dict(sorted(family_counter.items()))
    candidate_depth_by_source_origin_class = {
        "real_origin": class_counter.get("real_origin", 0),
        "semi_real_origin": class_counter.get("semi_real_origin", 0),
        "workflow_proximal_proxy": class_counter.get("workflow_proximal_proxy", 0),
    }

    post_expansion_mainline_count = len(mainline_combined)
    max_single_source_share_pct = _max_source_share_pct(mainline_combined)
    upstream_mainline_count = int(upstream_conclusion.get("mainline_real_origin_candidate_count") or 0)
    upstream_max_single_source_share_pct = float(
        upstream_conclusion.get("max_single_source_share_pct")
        or upstream_depth_probe.get("max_single_source_share_pct")
        or 0.0
    )
    admitted_real_source_count = sum(1 for row in admitted_sources if row.get("source_origin_class") == "real_origin")
    best_new_real_source_yield = max(
        [
            int(row.get("mainline_real_origin_candidate_count") or 0)
            for row in admitted_sources
            if row.get("source_origin_class") == "real_origin"
        ]
        or [0]
    )

    promoted_floor_met = (
        post_expansion_mainline_count >= PROMOTED_MAINLINE_MIN_COUNT
        and len(family_counter) >= PROMOTED_MAINLINE_MIN_FAMILY_COUNT
        and max_single_source_share_pct <= PROMOTED_MAX_SINGLE_SOURCE_SHARE_PCT
    )
    degraded_floor_met = (
        post_expansion_mainline_count >= DEGRADED_MAINLINE_MIN_COUNT
        and len(family_counter) >= DEGRADED_MAINLINE_MIN_FAMILY_COUNT
        and best_new_real_source_yield >= MIN_NEW_REAL_SOURCE_MAINLINE_YIELD
        and max_single_source_share_pct < upstream_max_single_source_share_pct
        and candidate_depth_by_source_origin_class.get("workflow_proximal_proxy", 0) == 0
    )

    if admitted_real_source_count == 0:
        expansion_status = "invalid"
    elif promoted_floor_met:
        expansion_status = "expansion_ready"
    elif degraded_floor_met:
        expansion_status = "expansion_partial"
    else:
        expansion_status = "invalid"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_pool_delta_and_diversity_report",
        "generated_at_utc": now_utc(),
        "status": "PASS" if expansion_status in {"expansion_ready", "expansion_partial"} else "FAIL",
        "baseline_mainline_real_origin_candidate_count": upstream_mainline_count,
        "post_expansion_mainline_real_origin_candidate_count": post_expansion_mainline_count,
        "mainline_count_delta_vs_v0_10_0": post_expansion_mainline_count - upstream_mainline_count,
        "candidate_depth_by_workflow_family": candidate_depth_by_workflow_family,
        "candidate_depth_by_source_origin_class": candidate_depth_by_source_origin_class,
        "max_single_source_share_pct": max_single_source_share_pct,
        "source_diversity_delta_vs_v0_10_0": {
            "baseline_max_single_source_share_pct": upstream_max_single_source_share_pct,
            "current_max_single_source_share_pct": max_single_source_share_pct,
            "max_single_source_share_pct_delta": round(
                max_single_source_share_pct - upstream_max_single_source_share_pct,
                1,
            ),
        },
        "new_source_mainline_contribution_table": new_source_mainline_contribution_table,
        "admitted_real_origin_source_count": admitted_real_source_count,
        "best_new_real_source_mainline_yield": best_new_real_source_yield,
        "promoted_floor_met": promoted_floor_met,
        "degraded_floor_met": degraded_floor_met,
        "needs_additional_real_origin_sources": not promoted_floor_met,
        "real_origin_source_expansion_status": expansion_status,
        "post_expansion_candidate_pool": admitted_combined,
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.1 Pool Delta And Diversity",
                "",
                f"- real_origin_source_expansion_status: `{expansion_status}`",
                f"- post_expansion_mainline_real_origin_candidate_count: `{post_expansion_mainline_count}`",
                f"- max_single_source_share_pct: `{max_single_source_share_pct}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.1 pool delta and diversity artifact.")
    parser.add_argument("--v1000-closeout", default=str(DEFAULT_V1000_CLOSEOUT_PATH))
    parser.add_argument("--v1000-governance-pack", default=str(DEFAULT_V1000_GOVERNANCE_PACK_PATH))
    parser.add_argument("--source-admission", default=str(DEFAULT_SOURCE_ADMISSION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_POOL_DELTA_OUT_DIR))
    args = parser.parse_args()
    payload = build_v101_pool_delta_and_diversity_report(
        v1000_closeout_path=str(args.v1000_closeout),
        v1000_governance_pack_path=str(args.v1000_governance_pack),
        source_admission_path=str(args.source_admission),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "real_origin_source_expansion_status": payload.get("real_origin_source_expansion_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
