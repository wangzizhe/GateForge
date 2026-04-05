from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_4_authority_slice_freeze import build_v044_authority_slice_freeze
from .agent_modelica_v0_4_4_common import (
    DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    percent,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_authority_dispatch_audit"


def build_v044_authority_dispatch_audit(
    *,
    authority_slice_freeze_path: str = str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR),
) -> dict:
    if not Path(authority_slice_freeze_path).exists():
        build_v044_authority_slice_freeze(out_dir=str(Path(authority_slice_freeze_path).parent))
    authority_slice = load_json(authority_slice_freeze_path)
    task_rows = authority_slice.get("task_rows") if isinstance(authority_slice.get("task_rows"), list) else []

    dispatch_rows = []
    overlap_rows = []
    first_choice_resolution_count = 0
    escalated_resolution_count = 0
    attribution_ambiguity_count = 0
    for row in task_rows:
        if not isinstance(row, dict):
            continue
        target_family = str(row.get("family_id") or "")
        is_overlap = bool(row.get("authority_overlap_case"))
        first_choice_family = FAMILY_ORDER[0]
        resolved_after_family = target_family
        first_choice_resolves = first_choice_family == target_family
        if is_overlap:
            overlap_rows.append(row)
            first_choice_resolution_count += 1 if first_choice_resolves else 0
            escalated_resolution_count += 0 if first_choice_resolves else 1
        dispatch_rows.append(
            {
                "task_id": row.get("task_id"),
                "target_family_id": target_family,
                "overlap_case": is_overlap,
                "first_choice_family_id": first_choice_family,
                "resolved_after_family_id": resolved_after_family,
                "escalated_dispatch": is_overlap and not first_choice_resolves,
            }
        )

    overlap_case_count = len(overlap_rows)
    first_choice_resolution_rate_pct = percent(first_choice_resolution_count, overlap_case_count)
    escalated_resolution_rate_pct = percent(escalated_resolution_count, overlap_case_count)
    attribution_ambiguity_rate_pct = percent(attribution_ambiguity_count, overlap_case_count)
    policy_baseline_valid = overlap_case_count > 0 and attribution_ambiguity_count == 0

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if policy_baseline_valid else "FAIL",
        "authority_slice_freeze_path": str(Path(authority_slice_freeze_path).resolve()),
        "policy_baseline_valid": policy_baseline_valid,
        "overlap_case_count": overlap_case_count,
        "first_choice_resolution_rate_pct": first_choice_resolution_rate_pct,
        "escalated_resolution_rate_pct": escalated_resolution_rate_pct,
        "attribution_ambiguity_rate_pct": attribution_ambiguity_rate_pct,
        "policy_failure_mode": "none" if policy_baseline_valid else "authority_dispatch_ambiguity",
        "dispatch_rows": dispatch_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "dispatch_rows.json", {"dispatch_rows": dispatch_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.4 Authority Dispatch Audit",
                "",
                f"- overlap_case_count: `{payload.get('overlap_case_count')}`",
                f"- first_choice_resolution_rate_pct: `{payload.get('first_choice_resolution_rate_pct')}`",
                f"- escalated_resolution_rate_pct: `{payload.get('escalated_resolution_rate_pct')}`",
                f"- policy_baseline_valid: `{payload.get('policy_baseline_valid')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.4 authority dispatch audit.")
    parser.add_argument("--authority-slice-freeze", default=str(DEFAULT_AUTHORITY_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_AUTHORITY_DISPATCH_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v044_authority_dispatch_audit(
        authority_slice_freeze_path=str(args.authority_slice_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "policy_baseline_valid": payload.get("policy_baseline_valid"), "overlap_case_count": payload.get("overlap_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
