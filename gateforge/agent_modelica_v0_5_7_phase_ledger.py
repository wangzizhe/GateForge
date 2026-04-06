from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_7_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V050_CLOSEOUT_PATH,
    DEFAULT_V051_CLOSEOUT_PATH,
    DEFAULT_V052_CLOSEOUT_PATH,
    DEFAULT_V053_CLOSEOUT_PATH,
    DEFAULT_V054_CLOSEOUT_PATH,
    DEFAULT_V055_CLOSEOUT_PATH,
    DEFAULT_V056_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_phase_ledger"


def build_v057_phase_ledger(
    *,
    v050_closeout_path: str = str(DEFAULT_V050_CLOSEOUT_PATH),
    v051_closeout_path: str = str(DEFAULT_V051_CLOSEOUT_PATH),
    v052_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    v053_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    v054_closeout_path: str = str(DEFAULT_V054_CLOSEOUT_PATH),
    v055_closeout_path: str = str(DEFAULT_V055_CLOSEOUT_PATH),
    v056_closeout_path: str = str(DEFAULT_V056_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    v050 = load_json(v050_closeout_path)
    v051 = load_json(v051_closeout_path)
    v052 = load_json(v052_closeout_path)
    v053 = load_json(v053_closeout_path)
    v054 = load_json(v054_closeout_path)
    v055 = load_json(v055_closeout_path)
    v056 = load_json(v056_closeout_path)

    widened_real_validation_supported = (v050.get("conclusion") or {}).get("version_decision") == "v0_5_0_widened_real_substrate_ready"
    boundary_mapping_supported = (v051.get("conclusion") or {}).get("version_decision") == "v0_5_1_boundary_map_ready"
    targeted_entry_ready = bool((v052.get("conclusion") or {}).get("entry_ready"))
    first_fix_ready = bool((v053.get("conclusion") or {}).get("first_fix_ready"))
    discovery_ready = bool((v054.get("conclusion") or {}).get("discovery_ready"))
    widened_branch_ready = bool((v055.get("conclusion") or {}).get("widened_ready"))
    promotion_supported = bool((v056.get("conclusion") or {}).get("promotion_supported"))

    phase_ledger_integrity_ok = all(
        [
            widened_real_validation_supported,
            boundary_mapping_supported,
            targeted_entry_ready,
            first_fix_ready,
            discovery_ready,
            widened_branch_ready,
            promotion_supported,
        ]
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if phase_ledger_integrity_ok else "FAIL",
        "phase_ledger_integrity_ok": phase_ledger_integrity_ok,
        "widened_real_validation_supported": widened_real_validation_supported,
        "boundary_mapping_supported": boundary_mapping_supported,
        "targeted_entry_ready": targeted_entry_ready,
        "first_fix_ready": first_fix_ready,
        "discovery_ready": discovery_ready,
        "widened_branch_ready": widened_branch_ready,
        "promotion_supported": promotion_supported,
        "promotion_level": (v056.get("conclusion") or {}).get("recommended_promotion_level"),
        "relation_to_parent_family": (v056.get("conclusion") or {}).get("relation_to_parent_family"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.7 Phase Ledger",
                "",
                f"- phase_ledger_integrity_ok: `{payload.get('phase_ledger_integrity_ok')}`",
                f"- promotion_level: `{payload.get('promotion_level')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.7 phase ledger.")
    parser.add_argument("--v0-5-0-closeout", default=str(DEFAULT_V050_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-1-closeout", default=str(DEFAULT_V051_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-4-closeout", default=str(DEFAULT_V054_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-5-closeout", default=str(DEFAULT_V055_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-6-closeout", default=str(DEFAULT_V056_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v057_phase_ledger(
        v050_closeout_path=str(args.v0_5_0_closeout),
        v051_closeout_path=str(args.v0_5_1_closeout),
        v052_closeout_path=str(args.v0_5_2_closeout),
        v053_closeout_path=str(args.v0_5_3_closeout),
        v054_closeout_path=str(args.v0_5_4_closeout),
        v055_closeout_path=str(args.v0_5_5_closeout),
        v056_closeout_path=str(args.v0_5_6_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_integrity_ok": payload.get("phase_ledger_integrity_ok")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
