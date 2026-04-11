from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_11_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V114_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v115_handoff_integrity(
    *,
    v114_closeout_path: str = str(DEFAULT_V114_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    closeout = load_json(v114_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}

    checks = {
        "version_decision_matches": conclusion.get("version_decision")
        == "v0_11_4_first_product_gap_thresholds_frozen",
        "handoff_mode_expected": conclusion.get("v0_11_5_handoff_mode")
        == "adjudicate_first_product_gap_profile_against_frozen_thresholds",
        "baseline_classification_expected": conclusion.get("baseline_classification_under_frozen_pack")
        == "product_gap_partial_but_interpretable",
        "anti_tautology_pass": bool(conclusion.get("anti_tautology_pass")),
        "integer_safe_pass": bool(conclusion.get("integer_safe_pass")),
        "execution_posture_semantics_preserved": bool(conclusion.get("execution_posture_semantics_preserved")),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": status,
        "handoff_integrity_status": status,
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_11_5_handoff_mode"),
        "upstream_baseline_classification": conclusion.get("baseline_classification_under_frozen_pack"),
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.11.5 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{status}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
                f"- upstream_baseline_classification: `{payload['upstream_baseline_classification']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.11.5 handoff integrity artifact.")
    parser.add_argument("--v114-closeout", default=str(DEFAULT_V114_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v115_handoff_integrity(
        v114_closeout_path=str(args.v114_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
