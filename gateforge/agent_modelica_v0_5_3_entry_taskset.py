from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_3_common import (
    DEFAULT_ENTRY_TASKSET_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V051_CLOSEOUT_PATH,
    DEFAULT_V052_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    TARGET_FIRST_FAILURE_BUCKET,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_3_handoff_integrity import build_v053_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_entry_taskset"


def build_v053_entry_taskset(
    *,
    v0_5_2_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    v0_5_1_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ENTRY_TASKSET_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v053_handoff_integrity(v0_5_2_closeout_path=v0_5_2_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    v052 = load_json(v0_5_2_closeout_path)
    v051 = load_json(v0_5_1_closeout_path)

    triage = v052.get("entry_triage") if isinstance(v052.get("entry_triage"), dict) else {}
    selected_ids = {str(x) for x in (triage.get("selected_entry_task_ids") or []) if str(x)}
    case_rows = ((v051.get("case_classification") or {}).get("case_rows") if isinstance(v051.get("case_classification"), dict) else []) or []

    promoted_case_table = []
    excluded_case_table = []
    for row in case_rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "")
        if task_id in selected_ids:
            promoted_case_table.append(
                {
                    "task_id": task_id,
                    "family_id": str(row.get("family_id") or ""),
                    "qualitative_bucket": str(row.get("qualitative_bucket") or ""),
                    "family_target_bucket": str(row.get("family_target_bucket") or TARGET_FIRST_FAILURE_BUCKET),
                }
            )
        elif str(row.get("family_id") or "") == "medium_redeclare_alignment":
            excluded_case_table.append(
                {
                    "task_id": task_id,
                    "qualitative_bucket": str(row.get("qualitative_bucket") or ""),
                    "exclusion_reason": "Outside the frozen promoted entry subtype or kept out to avoid mixing medium-cluster pressure into the fluid-network first-fix denominator.",
                }
            )

    entry_taskset_frozen = bool(integrity.get("handoff_integrity_ok")) and len(promoted_case_table) >= 4
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
        "entry_taskset_frozen": entry_taskset_frozen,
        "active_single_task_count": len(promoted_case_table),
        "entry_task_ids": [row["task_id"] for row in promoted_case_table],
        "promoted_case_table": promoted_case_table,
        "excluded_case_table": excluded_case_table,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.3 Entry Taskset",
                "",
                f"- entry_taskset_frozen: `{entry_taskset_frozen}`",
                f"- active_single_task_count: `{len(promoted_case_table)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.3 targeted-expansion entry taskset.")
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ENTRY_TASKSET_OUT_DIR))
    args = parser.parse_args()
    payload = build_v053_entry_taskset(
        v0_5_2_closeout_path=str(args.v0_5_2_closeout),
        v0_5_1_closeout_path=str(args.v0_5_1_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "active_single_task_count": payload.get("active_single_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
