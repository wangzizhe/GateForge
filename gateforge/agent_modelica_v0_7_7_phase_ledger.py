"""Block A: Phase Ledger Integrity.

Confirms that every version from v0.7.0 through v0.7.6 landed on the
expected version_decision string before v0.7.7 phase synthesis can proceed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_7_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V070_CLOSEOUT_PATH,
    DEFAULT_V071_CLOSEOUT_PATH,
    DEFAULT_V072_CLOSEOUT_PATH,
    DEFAULT_V073_CLOSEOUT_PATH,
    DEFAULT_V074_CLOSEOUT_PATH,
    DEFAULT_V075_CLOSEOUT_PATH,
    DEFAULT_V076_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)

_EXPECTED = {
    "v0.7.0": "v0_7_0_open_world_adjacent_substrate_ready",
    "v0.7.1": "v0_7_1_readiness_profile_ready",
    "v0.7.2": "v0_7_2_readiness_profile_stable",
    "v0.7.3": "v0_7_3_phase_decision_inputs_ready",
    "v0.7.4": "v0_7_4_open_world_readiness_partial_but_interpretable",
    "v0.7.5": "v0_7_5_open_world_readiness_partial_but_interpretable",
    "v0.7.6": "v0_7_6_phase_closeout_supported",
}


def build_v077_phase_ledger(
    *,
    v070_closeout_path: str = str(DEFAULT_V070_CLOSEOUT_PATH),
    v071_closeout_path: str = str(DEFAULT_V071_CLOSEOUT_PATH),
    v072_closeout_path: str = str(DEFAULT_V072_CLOSEOUT_PATH),
    v073_closeout_path: str = str(DEFAULT_V073_CLOSEOUT_PATH),
    v074_closeout_path: str = str(DEFAULT_V074_CLOSEOUT_PATH),
    v075_closeout_path: str = str(DEFAULT_V075_CLOSEOUT_PATH),
    v076_closeout_path: str = str(DEFAULT_V076_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    paths = {
        "v0.7.0": v070_closeout_path,
        "v0.7.1": v071_closeout_path,
        "v0.7.2": v072_closeout_path,
        "v0.7.3": v073_closeout_path,
        "v0.7.4": v074_closeout_path,
        "v0.7.5": v075_closeout_path,
        "v0.7.6": v076_closeout_path,
    }

    per_version: dict[str, dict] = {}
    for ver, path in paths.items():
        closeout = load_json(path)
        actual = (closeout.get("conclusion") or {}).get("version_decision")
        expected = _EXPECTED[ver]
        ok = actual == expected
        per_version[ver] = {
            "expected_version_decision": expected,
            "actual_version_decision": actual,
            "check_passed": ok,
        }

    all_passed = all(v["check_passed"] for v in per_version.values())

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if all_passed else "FAIL",
        "phase_ledger_integrity_status": "PASS" if all_passed else "FAIL",
        "per_version_checks": per_version,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    lines = ["# v0.7.7 Phase Ledger Integrity", "", f"- status: `{payload['status']}`", ""]
    for ver, info in per_version.items():
        mark = "PASS" if info["check_passed"] else "FAIL"
        lines.append(f"- {ver}: `{mark}` ({info['actual_version_decision']})")
    write_text(out_root / "summary.md", "\n".join(lines))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.7 phase ledger integrity check.")
    parser.add_argument("--v070-closeout", default=str(DEFAULT_V070_CLOSEOUT_PATH))
    parser.add_argument("--v071-closeout", default=str(DEFAULT_V071_CLOSEOUT_PATH))
    parser.add_argument("--v072-closeout", default=str(DEFAULT_V072_CLOSEOUT_PATH))
    parser.add_argument("--v073-closeout", default=str(DEFAULT_V073_CLOSEOUT_PATH))
    parser.add_argument("--v074-closeout", default=str(DEFAULT_V074_CLOSEOUT_PATH))
    parser.add_argument("--v075-closeout", default=str(DEFAULT_V075_CLOSEOUT_PATH))
    parser.add_argument("--v076-closeout", default=str(DEFAULT_V076_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v077_phase_ledger(
        v070_closeout_path=str(args.v070_closeout),
        v071_closeout_path=str(args.v071_closeout),
        v072_closeout_path=str(args.v072_closeout),
        v073_closeout_path=str(args.v073_closeout),
        v074_closeout_path=str(args.v074_closeout),
        v075_closeout_path=str(args.v075_closeout),
        v076_closeout_path=str(args.v076_closeout),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
