from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_6_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V052_CLOSEOUT_PATH,
    DEFAULT_V052_ENTRY_SPEC_PATH,
    DEFAULT_V053_CLOSEOUT_PATH,
    DEFAULT_V053_FIRST_FIX_PATH,
    DEFAULT_V054_CLOSEOUT_PATH,
    DEFAULT_V054_DISCOVERY_PATH,
    DEFAULT_V055_CLOSEOUT_PATH,
    DEFAULT_V055_WIDENED_ADJUDICATION_PATH,
    DEFAULT_V055_WIDENED_EXECUTION_PATH,
    SCHEMA_PREFIX,
    TARGET_ENTRY_PATTERN_ID,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_handoff_integrity"


def build_v056_handoff_integrity(
    *,
    v0_5_2_closeout_path: str = str(DEFAULT_V052_CLOSEOUT_PATH),
    v0_5_2_entry_spec_path: str = str(DEFAULT_V052_ENTRY_SPEC_PATH),
    v0_5_3_closeout_path: str = str(DEFAULT_V053_CLOSEOUT_PATH),
    v0_5_3_first_fix_path: str = str(DEFAULT_V053_FIRST_FIX_PATH),
    v0_5_4_closeout_path: str = str(DEFAULT_V054_CLOSEOUT_PATH),
    v0_5_4_discovery_path: str = str(DEFAULT_V054_DISCOVERY_PATH),
    v0_5_5_closeout_path: str = str(DEFAULT_V055_CLOSEOUT_PATH),
    v0_5_5_widened_adjudication_path: str = str(DEFAULT_V055_WIDENED_ADJUDICATION_PATH),
    v0_5_5_widened_execution_path: str = str(DEFAULT_V055_WIDENED_EXECUTION_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    v052 = load_json(v0_5_2_closeout_path)
    spec = load_json(v0_5_2_entry_spec_path)
    v053 = load_json(v0_5_3_closeout_path)
    v053_first_fix = load_json(v0_5_3_first_fix_path)
    v054 = load_json(v0_5_4_closeout_path)
    v054_discovery = load_json(v0_5_4_discovery_path)
    v055 = load_json(v0_5_5_closeout_path)
    v055_widened = load_json(v0_5_5_widened_adjudication_path)
    v055_execution = load_json(v0_5_5_widened_execution_path)

    entry_pattern_ok = (
        (v052.get("conclusion") or {}).get("selected_entry_pattern_id") == TARGET_ENTRY_PATTERN_ID
        and (v053.get("conclusion") or {}).get("entry_pattern_id") == TARGET_ENTRY_PATTERN_ID
        and (v054.get("conclusion") or {}).get("entry_pattern_id") == TARGET_ENTRY_PATTERN_ID
        and (v055.get("conclusion") or {}).get("entry_pattern_id") == TARGET_ENTRY_PATTERN_ID
    )
    entry_ready = bool((v052.get("conclusion") or {}).get("entry_ready"))
    first_fix_ready = bool((v053.get("conclusion") or {}).get("first_fix_ready")) and bool(v053_first_fix.get("first_fix_ready"))
    discovery_ready = bool((v054.get("conclusion") or {}).get("discovery_ready")) and bool(v054_discovery.get("discovery_ready"))
    widened_ready = bool((v055.get("conclusion") or {}).get("widened_ready")) and bool(v055_widened.get("widened_ready"))
    widened_task_count = int(((v055.get("widened_manifest") or {}).get("active_single_task_count")) or 0)
    boundedness_chain_intact = bool(spec.get("anti_expansion_boundary_rules")) and float(v055_execution.get("scope_creep_rate_pct") or 0.0) <= 0.0 and float(v055_execution.get("second_residual_bounded_rate_pct") or 0.0) > 0.0
    branch_stable = (v055.get("conclusion") or {}).get("branch_status") == "widened_and_stable"

    evidence_chain_integrity_ok = all(
        [
            entry_pattern_ok,
            entry_ready,
            first_fix_ready,
            discovery_ready,
            widened_ready,
            branch_stable,
        ]
    )
    promotion_admission_ready = bool(evidence_chain_integrity_ok and boundedness_chain_intact and widened_task_count >= 6)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if evidence_chain_integrity_ok else "FAIL",
        "entry_pattern_id": TARGET_ENTRY_PATTERN_ID,
        "entry_pattern_consistent": entry_pattern_ok,
        "entry_ready": entry_ready,
        "first_fix_ready": first_fix_ready,
        "discovery_ready": discovery_ready,
        "widened_ready": widened_ready,
        "widened_task_count": widened_task_count,
        "boundedness_chain_intact": boundedness_chain_intact,
        "evidence_chain_integrity_ok": evidence_chain_integrity_ok,
        "promotion_admission_ready": promotion_admission_ready,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.6 Handoff Integrity",
                "",
                f"- evidence_chain_integrity_ok: `{payload.get('evidence_chain_integrity_ok')}`",
                f"- boundedness_chain_intact: `{payload.get('boundedness_chain_intact')}`",
                f"- promotion_admission_ready: `{payload.get('promotion_admission_ready')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.6 handoff integrity summary.")
    parser.add_argument("--v0-5-2-closeout", default=str(DEFAULT_V052_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-2-entry-spec", default=str(DEFAULT_V052_ENTRY_SPEC_PATH))
    parser.add_argument("--v0-5-3-closeout", default=str(DEFAULT_V053_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-3-first-fix", default=str(DEFAULT_V053_FIRST_FIX_PATH))
    parser.add_argument("--v0-5-4-closeout", default=str(DEFAULT_V054_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-4-discovery", default=str(DEFAULT_V054_DISCOVERY_PATH))
    parser.add_argument("--v0-5-5-closeout", default=str(DEFAULT_V055_CLOSEOUT_PATH))
    parser.add_argument("--v0-5-5-widened-adjudication", default=str(DEFAULT_V055_WIDENED_ADJUDICATION_PATH))
    parser.add_argument("--v0-5-5-widened-execution", default=str(DEFAULT_V055_WIDENED_EXECUTION_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v056_handoff_integrity(
        v0_5_2_closeout_path=str(args.v0_5_2_closeout),
        v0_5_2_entry_spec_path=str(args.v0_5_2_entry_spec),
        v0_5_3_closeout_path=str(args.v0_5_3_closeout),
        v0_5_3_first_fix_path=str(args.v0_5_3_first_fix),
        v0_5_4_closeout_path=str(args.v0_5_4_closeout),
        v0_5_4_discovery_path=str(args.v0_5_4_discovery),
        v0_5_5_closeout_path=str(args.v0_5_5_closeout),
        v0_5_5_widened_adjudication_path=str(args.v0_5_5_widened_adjudication),
        v0_5_5_widened_execution_path=str(args.v0_5_5_widened_execution),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "promotion_admission_ready": payload.get("promotion_admission_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
