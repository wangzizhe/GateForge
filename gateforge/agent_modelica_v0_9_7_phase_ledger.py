from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_7_common import (
    DEFAULT_PHASE_LEDGER_OUT_DIR,
    DEFAULT_V090_CLOSEOUT_PATH,
    DEFAULT_V091_CLOSEOUT_PATH,
    DEFAULT_V092_CLOSEOUT_PATH,
    DEFAULT_V093_CLOSEOUT_PATH,
    DEFAULT_V094_CLOSEOUT_PATH,
    DEFAULT_V095_CLOSEOUT_PATH,
    DEFAULT_V096_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


EXPECTED = {
    "v0.9.0": "v0_9_0_candidate_pool_governance_partial",
    "v0.9.1": "v0_9_1_real_candidate_source_expansion_ready",
    "v0.9.2": "v0_9_2_first_expanded_authentic_workflow_substrate_ready",
    "v0.9.3": "v0_9_3_expanded_workflow_profile_characterized",
    "v0.9.4": "v0_9_4_expanded_workflow_thresholds_frozen",
    "v0.9.5": "v0_9_5_expanded_workflow_readiness_partial_but_interpretable",
    "v0.9.6": "v0_9_6_more_authentic_expansion_not_worth_it",
}


def _check(path: str, expected: str) -> dict:
    payload = load_json(path)
    actual = str((payload.get("conclusion") or {}).get("version_decision") or "")
    return {
        "expected_version_decision": expected,
        "actual_version_decision": actual,
        "check_passed": actual == expected,
    }


def build_v097_phase_ledger(
    *,
    v090_closeout_path: str = str(DEFAULT_V090_CLOSEOUT_PATH),
    v091_closeout_path: str = str(DEFAULT_V091_CLOSEOUT_PATH),
    v092_closeout_path: str = str(DEFAULT_V092_CLOSEOUT_PATH),
    v093_closeout_path: str = str(DEFAULT_V093_CLOSEOUT_PATH),
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    v095_closeout_path: str = str(DEFAULT_V095_CLOSEOUT_PATH),
    v096_closeout_path: str = str(DEFAULT_V096_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_PHASE_LEDGER_OUT_DIR),
) -> dict:
    checks = {
        "v0.9.0": _check(v090_closeout_path, EXPECTED["v0.9.0"]),
        "v0.9.1": _check(v091_closeout_path, EXPECTED["v0.9.1"]),
        "v0.9.2": _check(v092_closeout_path, EXPECTED["v0.9.2"]),
        "v0.9.3": _check(v093_closeout_path, EXPECTED["v0.9.3"]),
        "v0.9.4": _check(v094_closeout_path, EXPECTED["v0.9.4"]),
        "v0.9.5": _check(v095_closeout_path, EXPECTED["v0.9.5"]),
        "v0.9.6": _check(v096_closeout_path, EXPECTED["v0.9.6"]),
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
                "# v0.9.7 Phase Ledger",
                "",
                f"- phase_ledger_integrity_status: `{payload['phase_ledger_integrity_status']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.7 phase ledger.")
    parser.add_argument("--v090-closeout", default=str(DEFAULT_V090_CLOSEOUT_PATH))
    parser.add_argument("--v091-closeout", default=str(DEFAULT_V091_CLOSEOUT_PATH))
    parser.add_argument("--v092-closeout", default=str(DEFAULT_V092_CLOSEOUT_PATH))
    parser.add_argument("--v093-closeout", default=str(DEFAULT_V093_CLOSEOUT_PATH))
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--v095-closeout", default=str(DEFAULT_V095_CLOSEOUT_PATH))
    parser.add_argument("--v096-closeout", default=str(DEFAULT_V096_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PHASE_LEDGER_OUT_DIR))
    args = parser.parse_args()
    payload = build_v097_phase_ledger(
        v090_closeout_path=str(args.v090_closeout),
        v091_closeout_path=str(args.v091_closeout),
        v092_closeout_path=str(args.v092_closeout),
        v093_closeout_path=str(args.v093_closeout),
        v094_closeout_path=str(args.v094_closeout),
        v095_closeout_path=str(args.v095_closeout),
        v096_closeout_path=str(args.v096_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_ledger_integrity_status": payload.get("phase_ledger_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
