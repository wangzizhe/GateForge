from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_7_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V110_CLOSEOUT_PATH,
    DEFAULT_V111_CLOSEOUT_PATH,
    DEFAULT_V112_CLOSEOUT_PATH,
    DEFAULT_V113_CLOSEOUT_PATH,
    DEFAULT_V114_CLOSEOUT_PATH,
    DEFAULT_V115_CLOSEOUT_PATH,
    DEFAULT_V116_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED = {
    "v0.11.0": "v0_11_0_product_gap_governance_ready",
    "v0.11.1": "v0_11_1_first_product_gap_patch_pack_ready",
    "v0.11.2": "v0_11_2_first_product_gap_substrate_ready",
    "v0.11.3": "v0_11_3_first_product_gap_profile_characterized",
    "v0.11.4": "v0_11_4_first_product_gap_thresholds_frozen",
    "v0.11.5": "v0_11_5_first_product_gap_profile_partial_but_interpretable",
    "v0.11.6": "v0_11_6_more_bounded_product_gap_step_not_worth_it",
}


def _check(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def build_v117_phase_ledger(
    *,
    v110_closeout_path: str = str(DEFAULT_V110_CLOSEOUT_PATH),
    v111_closeout_path: str = str(DEFAULT_V111_CLOSEOUT_PATH),
    v112_closeout_path: str = str(DEFAULT_V112_CLOSEOUT_PATH),
    v113_closeout_path: str = str(DEFAULT_V113_CLOSEOUT_PATH),
    v114_closeout_path: str = str(DEFAULT_V114_CLOSEOUT_PATH),
    v115_closeout_path: str = str(DEFAULT_V115_CLOSEOUT_PATH),
    v116_closeout_path: str = str(DEFAULT_V116_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.11.0": _check(v110_closeout_path, EXPECTED["v0.11.0"]),
        "v0.11.1": _check(v111_closeout_path, EXPECTED["v0.11.1"]),
        "v0.11.2": _check(v112_closeout_path, EXPECTED["v0.11.2"]),
        "v0.11.3": _check(v113_closeout_path, EXPECTED["v0.11.3"]),
        "v0.11.4": _check(v114_closeout_path, EXPECTED["v0.11.4"]),
        "v0.11.5": _check(v115_closeout_path, EXPECTED["v0.11.5"]),
        "v0.11.6": _check(v116_closeout_path, EXPECTED["v0.11.6"]),
    }
    passed = all(item["check_passed"] for item in checks.values())
    v116 = load_json(v116_closeout_path)
    latest_handoff_mode = str(((v116.get("conclusion") or {}).get("v0_11_7_handoff_mode") or ""))
    handoff_mode_ok = latest_handoff_mode == "prepare_v0_11_phase_synthesis"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_phase_ledger",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed and handoff_mode_ok else "FAIL",
        "phase_ledger_status": "PASS" if passed and handoff_mode_ok else "FAIL",
        "version_chain": list(EXPECTED.values()),
        "phase_question": "workflow_to_product_gap_evaluation",
        "current_phase_answer_shape": "product_gap_partial_but_interpretable_with_explicit_non_worthed_next_step",
        "latest_handoff_mode": latest_handoff_mode,
        "per_version_checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.7 Phase Ledger",
                "",
                f"- phase_ledger_status: `{payload['phase_ledger_status']}`",
                f"- latest_handoff_mode: `{latest_handoff_mode}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.7 phase ledger.")
    parser.add_argument("--v110-closeout", default=str(DEFAULT_V110_CLOSEOUT_PATH))
    parser.add_argument("--v111-closeout", default=str(DEFAULT_V111_CLOSEOUT_PATH))
    parser.add_argument("--v112-closeout", default=str(DEFAULT_V112_CLOSEOUT_PATH))
    parser.add_argument("--v113-closeout", default=str(DEFAULT_V113_CLOSEOUT_PATH))
    parser.add_argument("--v114-closeout", default=str(DEFAULT_V114_CLOSEOUT_PATH))
    parser.add_argument("--v115-closeout", default=str(DEFAULT_V115_CLOSEOUT_PATH))
    parser.add_argument("--v116-closeout", default=str(DEFAULT_V116_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v117_phase_ledger(
        v110_closeout_path=str(args.v110_closeout),
        v111_closeout_path=str(args.v111_closeout),
        v112_closeout_path=str(args.v112_closeout),
        v113_closeout_path=str(args.v113_closeout),
        v114_closeout_path=str(args.v114_closeout),
        v115_closeout_path=str(args.v115_closeout),
        v116_closeout_path=str(args.v116_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_status": payload.get("phase_ledger_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
