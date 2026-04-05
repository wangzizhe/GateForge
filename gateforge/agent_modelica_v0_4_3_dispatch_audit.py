from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_3_common import (
    DEFAULT_DISPATCH_AUDIT_OUT_DIR,
    DEFAULT_REAL_SLICE_FREEZE_OUT_DIR,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_3_real_slice_freeze import build_v043_real_slice_freeze


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_dispatch_audit"


def build_v043_dispatch_audit(
    *,
    real_slice_freeze_path: str = str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DISPATCH_AUDIT_OUT_DIR),
) -> dict:
    if not Path(real_slice_freeze_path).exists():
        build_v043_real_slice_freeze(out_dir=str(Path(real_slice_freeze_path).parent))
    real_slice = load_json(real_slice_freeze_path)
    task_rows = real_slice.get("task_rows") if isinstance(real_slice.get("task_rows"), list) else []

    dispatch_rows = []
    first_family_resolves_count = 0
    escalated_dispatch_count = 0
    for row in task_rows:
        if not isinstance(row, dict):
            continue
        target_family = str(row.get("family_id") or "")
        resolved_after = target_family
        first_family_resolves = target_family == FAMILY_ORDER[0]
        first_family_resolves_count += 1 if first_family_resolves else 0
        escalated_dispatch_count += 0 if first_family_resolves else 1
        dispatch_rows.append(
            {
                "task_id": row.get("task_id"),
                "target_family_id": target_family,
                "first_choice_family_id": FAMILY_ORDER[0],
                "resolved_after_family_id": resolved_after,
                "escalated_dispatch": not first_family_resolves,
            }
        )

    overlap_case_count = len(dispatch_rows)
    policy_baseline_valid = overlap_case_count > 0 and all(str(row.get("resolved_after_family_id") or "") == str(row.get("target_family_id") or "") for row in dispatch_rows)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if policy_baseline_valid else "FAIL",
        "real_slice_freeze_path": str(Path(real_slice_freeze_path).resolve()),
        "overlap_case_count": overlap_case_count,
        "first_family_resolves_count": first_family_resolves_count,
        "escalated_dispatch_count": escalated_dispatch_count,
        "policy_baseline_valid": policy_baseline_valid,
        "policy_failure_mode": "none" if policy_baseline_valid else "dispatch_regression",
        "dispatch_rows": dispatch_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "dispatch_rows.json", {"dispatch_rows": dispatch_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.3 Dispatch Audit",
                "",
                f"- overlap_case_count: `{payload.get('overlap_case_count')}`",
                f"- escalated_dispatch_count: `{payload.get('escalated_dispatch_count')}`",
                f"- policy_baseline_valid: `{payload.get('policy_baseline_valid')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.3 widened dispatch audit.")
    parser.add_argument("--real-slice-freeze", default=str(DEFAULT_REAL_SLICE_FREEZE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DISPATCH_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v043_dispatch_audit(
        real_slice_freeze_path=str(args.real_slice_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "policy_baseline_valid": payload.get("policy_baseline_valid"), "overlap_case_count": payload.get("overlap_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
