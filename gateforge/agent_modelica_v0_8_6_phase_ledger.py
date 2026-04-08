from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_8_6_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V080_CLOSEOUT_PATH,
    DEFAULT_V081_CLOSEOUT_PATH,
    DEFAULT_V082_CLOSEOUT_PATH,
    DEFAULT_V083_CLOSEOUT_PATH,
    DEFAULT_V084_CLOSEOUT_PATH,
    DEFAULT_V085_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED = {
    "v0.8.0": "v0_8_0_workflow_proximal_substrate_ready",
    "v0.8.1": "v0_8_1_workflow_readiness_profile_characterized",
    "v0.8.2": "v0_8_2_workflow_readiness_thresholds_frozen",
    "v0.8.3": "v0_8_3_threshold_pack_validated",
    "v0.8.4": "v0_8_4_workflow_readiness_partial_but_interpretable",
    "v0.8.5": "v0_8_5_same_logic_refinement_not_worth_it",
}


def _check(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def build_v086_phase_ledger(
    *,
    v080_closeout_path: str = str(DEFAULT_V080_CLOSEOUT_PATH),
    v081_closeout_path: str = str(DEFAULT_V081_CLOSEOUT_PATH),
    v082_closeout_path: str = str(DEFAULT_V082_CLOSEOUT_PATH),
    v083_closeout_path: str = str(DEFAULT_V083_CLOSEOUT_PATH),
    v084_closeout_path: str = str(DEFAULT_V084_CLOSEOUT_PATH),
    v085_closeout_path: str = str(DEFAULT_V085_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.8.0": _check(v080_closeout_path, EXPECTED["v0.8.0"]),
        "v0.8.1": _check(v081_closeout_path, EXPECTED["v0.8.1"]),
        "v0.8.2": _check(v082_closeout_path, EXPECTED["v0.8.2"]),
        "v0.8.3": _check(v083_closeout_path, EXPECTED["v0.8.3"]),
        "v0.8.4": _check(v084_closeout_path, EXPECTED["v0.8.4"]),
        "v0.8.5": _check(v085_closeout_path, EXPECTED["v0.8.5"]),
    }
    passed = all(item["check_passed"] for item in checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "phase_ledger_integrity_status": "PASS" if passed else "FAIL",
        "per_version_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.6 Phase Ledger",
                "",
                f"- phase_ledger_integrity_status: `{payload['phase_ledger_integrity_status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.6 phase ledger.")
    parser.add_argument("--v080-closeout", default=str(DEFAULT_V080_CLOSEOUT_PATH))
    parser.add_argument("--v081-closeout", default=str(DEFAULT_V081_CLOSEOUT_PATH))
    parser.add_argument("--v082-closeout", default=str(DEFAULT_V082_CLOSEOUT_PATH))
    parser.add_argument("--v083-closeout", default=str(DEFAULT_V083_CLOSEOUT_PATH))
    parser.add_argument("--v084-closeout", default=str(DEFAULT_V084_CLOSEOUT_PATH))
    parser.add_argument("--v085-closeout", default=str(DEFAULT_V085_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v086_phase_ledger(
        v080_closeout_path=str(args.v080_closeout),
        v081_closeout_path=str(args.v081_closeout),
        v082_closeout_path=str(args.v082_closeout),
        v083_closeout_path=str(args.v083_closeout),
        v084_closeout_path=str(args.v084_closeout),
        v085_closeout_path=str(args.v085_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_integrity_status": payload.get("phase_ledger_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
