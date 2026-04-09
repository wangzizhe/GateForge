from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_9_5_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V094_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v095_handoff_integrity(
    *,
    v094_closeout_path: str = str(DEFAULT_V094_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    closeout = load_json(v094_closeout_path)
    conclusion = closeout.get("conclusion") if isinstance(closeout.get("conclusion"), dict) else {}

    checks = {
        "version_decision_ok": conclusion.get("version_decision")
        == "v0_9_4_expanded_workflow_thresholds_frozen",
        "handoff_mode_ok": conclusion.get("v0_9_5_handoff_mode")
        == "adjudicate_expanded_workflow_readiness_against_frozen_thresholds",
        "baseline_classification_ok": conclusion.get("baseline_classification_under_frozen_pack")
        == "expanded_workflow_readiness_partial_but_interpretable",
        "anti_tautology_ok": bool(conclusion.get("anti_tautology_pass")),
        "integer_safe_ok": bool(conclusion.get("integer_safe_pass")),
        "threshold_ordering_ok": bool(conclusion.get("threshold_ordering_pass")),
        "execution_posture_ok": bool(conclusion.get("execution_posture_pass")),
    }
    passed = all(checks.values())
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": "PASS" if passed else "FAIL",
        "handoff_integrity_status": "PASS" if passed else "FAIL",
        "checks": checks,
        "upstream_version_decision": conclusion.get("version_decision"),
        "upstream_handoff_mode": conclusion.get("v0_9_5_handoff_mode"),
        "baseline_classification_under_frozen_pack": conclusion.get("baseline_classification_under_frozen_pack"),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.5 Handoff Integrity",
                "",
                f"- status: `{payload['status']}`",
                f"- upstream_version_decision: `{payload['upstream_version_decision']}`",
                f"- upstream_handoff_mode: `{payload['upstream_handoff_mode']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.5 handoff integrity summary.")
    parser.add_argument("--v094-closeout", default=str(DEFAULT_V094_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v095_handoff_integrity(v094_closeout_path=str(args.v094_closeout), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "handoff_integrity_status": payload.get("handoff_integrity_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
