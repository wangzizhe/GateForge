from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_14_2_common import (
    DEFAULT_HANDOFF_INTEGRITY_OUT_DIR,
    DEFAULT_V141_CLOSEOUT_PATH,
    EXPECTED_V141_EFFECT_CLASSES,
    EXPECTED_V141_HANDOFF_MODE,
    EXPECTED_V141_VERSION_DECISIONS,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v142_handoff_integrity(
    *,
    v141_closeout_path: str = str(DEFAULT_V141_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR),
) -> dict:
    upstream = load_json(v141_closeout_path)
    conclusion = upstream.get("conclusion") if isinstance(upstream.get("conclusion"), dict) else {}

    upstream_version_decision = str(conclusion.get("version_decision") or "")
    upstream_broader_change_effect_class = str(conclusion.get("broader_change_effect_class") or "")
    pre_intervention_run_reference = conclusion.get("pre_intervention_run_reference")
    post_intervention_run_reference = conclusion.get("post_intervention_run_reference")
    upstream_same_execution_source = bool(conclusion.get("same_execution_source"))
    upstream_same_case_requirement_met = bool(conclusion.get("same_case_requirement_met"))
    upstream_handoff_mode = str(conclusion.get("v0_14_2_handoff_mode") or "")

    checks = {
        "version_decision_ok": upstream_version_decision in EXPECTED_V141_VERSION_DECISIONS,
        "broader_change_effect_class_ok": upstream_broader_change_effect_class in EXPECTED_V141_EFFECT_CLASSES,
        "pre_intervention_run_reference_ok": bool(pre_intervention_run_reference),
        "post_intervention_run_reference_ok": bool(post_intervention_run_reference),
        "same_execution_source_ok": upstream_same_execution_source,
        "same_case_requirement_met_ok": upstream_same_case_requirement_met,
        "handoff_mode_ok": upstream_handoff_mode == EXPECTED_V141_HANDOFF_MODE,
    }
    handoff_integrity_status = "PASS" if all(checks.values()) else "FAIL"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_handoff_integrity",
        "generated_at_utc": now_utc(),
        "status": handoff_integrity_status,
        "handoff_integrity_status": handoff_integrity_status,
        "upstream_version_decision": upstream_version_decision,
        "upstream_broader_change_effect_class": upstream_broader_change_effect_class,
        "pre_intervention_run_reference": pre_intervention_run_reference,
        "post_intervention_run_reference": post_intervention_run_reference,
        "upstream_same_execution_source": upstream_same_execution_source,
        "upstream_same_case_requirement_met": upstream_same_case_requirement_met,
        "upstream_handoff_mode": upstream_handoff_mode,
        "checks": checks,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.14.2 Handoff Integrity",
                "",
                f"- handoff_integrity_status: `{handoff_integrity_status}`",
                f"- upstream_version_decision: `{upstream_version_decision}`",
                f"- upstream_broader_change_effect_class: `{upstream_broader_change_effect_class}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.14.2 handoff integrity artifact.")
    parser.add_argument("--v141-closeout", default=str(DEFAULT_V141_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_HANDOFF_INTEGRITY_OUT_DIR))
    args = parser.parse_args()
    payload = build_v142_handoff_integrity(
        v141_closeout_path=str(args.v141_closeout),
        out_dir=str(args.out_dir),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "handoff_integrity_status": payload.get("handoff_integrity_status"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
