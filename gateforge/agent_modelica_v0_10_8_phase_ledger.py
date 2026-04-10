from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_8_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V100_CLOSEOUT_PATH,
    DEFAULT_V101_CLOSEOUT_PATH,
    DEFAULT_V102_CLOSEOUT_PATH,
    DEFAULT_V103_CLOSEOUT_PATH,
    DEFAULT_V104_CLOSEOUT_PATH,
    DEFAULT_V105_CLOSEOUT_PATH,
    DEFAULT_V106_CLOSEOUT_PATH,
    DEFAULT_V107_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED = {
    "v0.10.0": "v0_10_0_real_origin_candidate_governance_partial",
    "v0.10.1": "v0_10_1_real_origin_source_expansion_partial",
    "v0.10.2": "v0_10_2_real_origin_source_expansion_ready",
    "v0.10.3": "v0_10_3_first_real_origin_workflow_substrate_ready",
    "v0.10.4": "v0_10_4_first_real_origin_workflow_profile_characterized",
    "v0.10.5": "v0_10_5_first_real_origin_workflow_thresholds_frozen",
    "v0.10.6": "v0_10_6_first_real_origin_workflow_readiness_partial_but_interpretable",
    "v0.10.7": "v0_10_7_more_bounded_real_origin_step_not_worth_it",
}


def _check(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def build_v108_phase_ledger(
    *,
    v100_closeout_path: str = str(DEFAULT_V100_CLOSEOUT_PATH),
    v101_closeout_path: str = str(DEFAULT_V101_CLOSEOUT_PATH),
    v102_closeout_path: str = str(DEFAULT_V102_CLOSEOUT_PATH),
    v103_closeout_path: str = str(DEFAULT_V103_CLOSEOUT_PATH),
    v104_closeout_path: str = str(DEFAULT_V104_CLOSEOUT_PATH),
    v105_closeout_path: str = str(DEFAULT_V105_CLOSEOUT_PATH),
    v106_closeout_path: str = str(DEFAULT_V106_CLOSEOUT_PATH),
    v107_closeout_path: str = str(DEFAULT_V107_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.10.0": _check(v100_closeout_path, EXPECTED["v0.10.0"]),
        "v0.10.1": _check(v101_closeout_path, EXPECTED["v0.10.1"]),
        "v0.10.2": _check(v102_closeout_path, EXPECTED["v0.10.2"]),
        "v0.10.3": _check(v103_closeout_path, EXPECTED["v0.10.3"]),
        "v0.10.4": _check(v104_closeout_path, EXPECTED["v0.10.4"]),
        "v0.10.5": _check(v105_closeout_path, EXPECTED["v0.10.5"]),
        "v0.10.6": _check(v106_closeout_path, EXPECTED["v0.10.6"]),
        "v0.10.7": _check(v107_closeout_path, EXPECTED["v0.10.7"]),
    }
    passed = all(item["check_passed"] for item in checks.values())
    v107 = load_json(v107_closeout_path)
    handoff_mode_ok = str(((v107.get("conclusion") or {}).get("v0_10_8_handoff_mode") or "")) == "prepare_v0_10_phase_synthesis"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed and handoff_mode_ok else "FAIL",
        "phase_ledger_integrity_status": "PASS" if passed and handoff_mode_ok else "FAIL",
        "per_version_checks": checks,
        "v107_handoff_mode_ok": handoff_mode_ok,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.8 Phase Ledger",
                "",
                f"- phase_ledger_integrity_status: `{payload['phase_ledger_integrity_status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.8 phase ledger.")
    parser.add_argument("--v100-closeout", default=str(DEFAULT_V100_CLOSEOUT_PATH))
    parser.add_argument("--v101-closeout", default=str(DEFAULT_V101_CLOSEOUT_PATH))
    parser.add_argument("--v102-closeout", default=str(DEFAULT_V102_CLOSEOUT_PATH))
    parser.add_argument("--v103-closeout", default=str(DEFAULT_V103_CLOSEOUT_PATH))
    parser.add_argument("--v104-closeout", default=str(DEFAULT_V104_CLOSEOUT_PATH))
    parser.add_argument("--v105-closeout", default=str(DEFAULT_V105_CLOSEOUT_PATH))
    parser.add_argument("--v106-closeout", default=str(DEFAULT_V106_CLOSEOUT_PATH))
    parser.add_argument("--v107-closeout", default=str(DEFAULT_V107_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v108_phase_ledger(
        v100_closeout_path=str(args.v100_closeout),
        v101_closeout_path=str(args.v101_closeout),
        v102_closeout_path=str(args.v102_closeout),
        v103_closeout_path=str(args.v103_closeout),
        v104_closeout_path=str(args.v104_closeout),
        v105_closeout_path=str(args.v105_closeout),
        v106_closeout_path=str(args.v106_closeout),
        v107_closeout_path=str(args.v107_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_integrity_status": payload.get("phase_ledger_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
