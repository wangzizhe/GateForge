from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_4_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V053_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v054_handoff_integrity(
    *,
    v0_5_3_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v0_5_3_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}
    adjudication = closeout.get("first_fix_adjudication") if isinstance(closeout.get("first_fix_adjudication"), dict) else {}
    taskset = closeout.get("entry_taskset") if isinstance(closeout.get("entry_taskset"), dict) else {}

    first_fix_lane_confirmed = bool(conclusion.get("first_fix_ready"))
    entry_pattern_id_confirmed = str(conclusion.get("entry_pattern_id") or "") == TARGET_ENTRY_PATTERN_ID
    anti_expansion_boundary_intact = bool((adjudication.get("entry_execution_interpretation") or {}).get("anti_expansion_boundary_preserved"))
    denominator_stable = bool(taskset.get("entry_taskset_frozen"))
    handoff_integrity_ok = first_fix_lane_confirmed and entry_pattern_id_confirmed and anti_expansion_boundary_intact and denominator_stable

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "v0_5_3_closeout_path": str(Path(v0_5_3_closeout_path).resolve()),
        "handoff_integrity_ok": handoff_integrity_ok,
        "first_fix_lane_confirmed": first_fix_lane_confirmed,
        "entry_pattern_id_confirmed": entry_pattern_id_confirmed,
        "anti_expansion_boundary_intact": anti_expansion_boundary_intact,
        "denominator_stable": denominator_stable,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.4 Handoff Integrity",
                "",
                f"- handoff_integrity_ok: `{handoff_integrity_ok}`",
                f"- first_fix_lane_confirmed: `{first_fix_lane_confirmed}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.4 discovery-probe handoff integrity check.")
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v054_handoff_integrity(v0_5_3_closeout_path=str(args.v0_5_3_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_ok": payload.get("handoff_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
