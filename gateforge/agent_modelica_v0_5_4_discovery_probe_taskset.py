from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_4_common import (
    DEFAULT_DISCOVERY_TASKSET_OUT_DIR,
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V053_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_4_handoff_integrity import build_v054_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_discovery_probe_taskset"


def build_v054_discovery_probe_taskset(
    *,
    v0_5_3_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v054_handoff_integrity(v0_5_3_closeout_path=v0_5_3_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    closeout = load_json(v0_5_3_closeout_path)
    entry_taskset = closeout.get("entry_taskset") if isinstance(closeout.get("entry_taskset"), dict) else {}
    promoted_case_table = entry_taskset.get("promoted_case_table") if isinstance(entry_taskset.get("promoted_case_table"), list) else []
    excluded_case_table = entry_taskset.get("excluded_case_table") if isinstance(entry_taskset.get("excluded_case_table"), list) else []

    probe_case_table = []
    for row in promoted_case_table:
        if not isinstance(row, dict):
            continue
        probe_case_table.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
                "residual_probe_expectation": "bounded_local_medium_redeclare_residual",
            }
        )

    discovery_probe_taskset_frozen = bool(integrity.get("handoff_integrity_ok")) and len(probe_case_table) >= 4
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
        "discovery_probe_taskset_frozen": discovery_probe_taskset_frozen,
        "active_probe_task_count": len(probe_case_table),
        "probe_task_ids": [row["task_id"] for row in probe_case_table],
        "probe_case_table": probe_case_table,
        "excluded_probe_case_table": excluded_case_table,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.4 Discovery Probe Taskset",
                "",
                f"- discovery_probe_taskset_frozen: `{discovery_probe_taskset_frozen}`",
                f"- active_probe_task_count: `{len(probe_case_table)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.4 discovery probe taskset.")
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DISCOVERY_TASKSET_OUT_DIR))
    args = parser.parse_args()
    payload = build_v054_discovery_probe_taskset(
        v0_5_3_closeout_path=str(args.v0_5_3_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "active_probe_task_count": payload.get("active_probe_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
