from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_5_common import (
    DEFAULT_SLICE_LOCK_OUT_DIR,
    DEFAULT_V044_AUTHORITY_SLICE_PATH,
    FAMILY_ORDER,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_policy_slice_lock"


def build_v045_policy_slice_lock(
    *,
    v0_4_4_authority_slice_path: str = str(DEFAULT_V044_AUTHORITY_SLICE_PATH),
    out_dir: str = str(DEFAULT_SLICE_LOCK_OUT_DIR),
) -> dict:
    authority_slice = load_json(v0_4_4_authority_slice_path)
    task_rows = authority_slice.get("task_rows") if isinstance(authority_slice.get("task_rows"), list) else []

    family_breakdown = authority_slice.get("real_authority_family_breakdown") or {}
    complexity_breakdown = authority_slice.get("real_authority_complexity_breakdown") or {}
    overlap_case_count = int(authority_slice.get("real_authority_overlap_case_count") or 0)
    policy_comparison_slice_locked = (
        bool(authority_slice.get("authority_slice_ready"))
        and len(task_rows) == int(authority_slice.get("real_authority_slice_task_count") or 0)
        and all(int(family_breakdown.get(family_id) or 0) > 0 for family_id in FAMILY_ORDER)
        and overlap_case_count > 0
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if policy_comparison_slice_locked else "FAIL",
        "authority_slice_path": str(Path(v0_4_4_authority_slice_path).resolve()),
        "policy_comparison_slice_locked": policy_comparison_slice_locked,
        "task_count": len(task_rows),
        "family_breakdown": family_breakdown,
        "complexity_breakdown": complexity_breakdown,
        "overlap_case_count": overlap_case_count,
        "task_rows": task_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "task_rows.json", {"task_rows": task_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.5 Policy Slice Lock",
                "",
                f"- policy_comparison_slice_locked: `{payload.get('policy_comparison_slice_locked')}`",
                f"- task_count: `{payload.get('task_count')}`",
                f"- overlap_case_count: `{payload.get('overlap_case_count')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.5 policy comparison slice lock.")
    parser.add_argument("--v0-4-4-authority-slice", default=str(DEFAULT_V044_AUTHORITY_SLICE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_SLICE_LOCK_OUT_DIR))
    args = parser.parse_args()
    payload = build_v045_policy_slice_lock(
        v0_4_4_authority_slice_path=str(args.v0_4_4_authority_slice),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "policy_comparison_slice_locked": payload.get("policy_comparison_slice_locked")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
