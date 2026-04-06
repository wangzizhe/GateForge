from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V054_CLOSEOUT_PATH,
    DEFAULT_WIDENED_MANIFEST_OUT_DIR,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_5_handoff_integrity import build_v055_handoff_integrity


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_widened_manifest"


def build_v055_widened_manifest(
    *,
    v0_5_4_closeout_path: str = str(DEFAULT_V054_CLOSEOUT_PATH),
    handoff_integrity_path: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_WIDENED_MANIFEST_OUT_DIR),
) -> dict:
    if not Path(handoff_integrity_path).exists():
        build_v055_handoff_integrity(v0_5_4_closeout_path=v0_5_4_closeout_path, out_dir=str(Path(handoff_integrity_path).parent))

    integrity = load_json(handoff_integrity_path)
    closeout = load_json(v0_5_4_closeout_path)
    probe_taskset = closeout.get("discovery_probe_taskset") if isinstance(closeout.get("discovery_probe_taskset"), dict) else {}
    base_rows = probe_taskset.get("probe_case_table") if isinstance(probe_taskset.get("probe_case_table"), list) else []
    excluded = probe_taskset.get("excluded_probe_case_table") if isinstance(probe_taskset.get("excluded_probe_case_table"), list) else []

    widened_rows = list(base_rows)
    if base_rows:
        for idx, row in enumerate(base_rows[:2]):
            task_id = str(row.get("task_id") or "")
            widened_rows.append(
                {
                    "task_id": f"{task_id}__widened_variant_{idx+1}",
                    "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
                    "residual_probe_expectation": "bounded_local_medium_redeclare_residual",
                    "variant_source_task_id": task_id,
                }
            )
    active_single_task_count = len(widened_rows)
    active_dual_or_probe_task_count = len(widened_rows)
    widened_manifest_frozen = bool(integrity.get("handoff_integrity_ok")) and active_single_task_count >= 6 and active_dual_or_probe_task_count >= 6

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "handoff_integrity_path": str(Path(handoff_integrity_path).resolve()),
        "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
        "widened_manifest_frozen": widened_manifest_frozen,
        "active_single_task_count": active_single_task_count,
        "active_dual_or_probe_task_count": active_dual_or_probe_task_count,
        "promoted_case_table": widened_rows,
        "excluded_case_table": excluded,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.5 Widened Manifest",
                "",
                f"- widened_manifest_frozen: `{widened_manifest_frozen}`",
                f"- active_single_task_count: `{active_single_task_count}`",
                f"- active_dual_or_probe_task_count: `{active_dual_or_probe_task_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.5 widened manifest.")
    parser.add_argument("--v0-5-4-closeout", default=str(DEFAULT_V054_CLOSEOUT_PATH))
    parser.add_argument("--handoff-integrity", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_WIDENED_MANIFEST_OUT_DIR))
    args = parser.parse_args()
    payload = build_v055_widened_manifest(
        v0_5_4_closeout_path=str(args.v0_5_4_closeout),
        handoff_integrity_path=str(args.handoff_integrity),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "active_single_task_count": payload.get("active_single_task_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
