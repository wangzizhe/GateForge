from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_34_common import (
    DEFAULT_REAL_DIST_OUT_DIR,
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V0_4_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_34_real_distribution_synthesis import build_v0334_real_distribution_synthesis
from .agent_modelica_v0_3_34_stop_condition_audit import build_v0334_stop_condition_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_handoff"


def build_v0334_v0_4_handoff(
    *,
    stop_audit_path: str = str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"),
    real_distribution_synthesis_path: str = str(DEFAULT_REAL_DIST_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_4_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(stop_audit_path).exists():
        build_v0334_stop_condition_audit(out_dir=str(Path(stop_audit_path).parent))
    if not Path(real_distribution_synthesis_path).exists():
        build_v0334_real_distribution_synthesis(out_dir=str(Path(real_distribution_synthesis_path).parent))

    stop_audit = load_json(stop_audit_path)
    real_dist = load_json(real_distribution_synthesis_path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "stop_condition_audit_path": str(Path(stop_audit_path).resolve()),
        "real_distribution_synthesis_path": str(Path(real_distribution_synthesis_path).resolve()),
        "v0_4_primary_eval_question": "Does the agent measurably improve when trained or conditioned on the synthetic stage_2 curriculum built in v0.3.x?",
        "v0_4_required_real_back_check": bool(real_dist.get("v0_4_required_real_back_check")),
        "v0_4_multi_family_policy_requirement": {
            "overlap_case_definition": "A case whose first failure can be interpreted as matching more than one stage_2 family target bucket.",
            "dispatch_priority_rule": [
                "Prefer the narrowest bounded patch contract first.",
                "Default precedence: component_api_alignment -> local_interface_alignment -> medium_redeclare_alignment.",
                "Escalate only if the earlier family does not produce signature advance."
            ],
            "policy_mechanism": "stage-gated_with_arbitration",
            "evaluation_role": "authority_evaluation_requirement",
        },
        "v0_4_non_goals": [
            "default_new_family_construction",
            "synthetic_only_learning_gain_claim",
            "open_world_repair_claim",
        ],
        "summary": "v0.4.x should shift from family construction to learning effectiveness, but it must include a real-distribution back-check and an explicit multi-family dispatch policy.",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.34 v0.4 Handoff",
                "",
                f"- v0_4_required_real_back_check: `{payload.get('v0_4_required_real_back_check')}`",
                f"- policy_mechanism: `{((payload.get('v0_4_multi_family_policy_requirement') or {}).get('policy_mechanism'))}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.34 v0.4 handoff.")
    parser.add_argument("--stop-audit", default=str(DEFAULT_STOP_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--real-distribution-synthesis", default=str(DEFAULT_REAL_DIST_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0334_v0_4_handoff(
        stop_audit_path=str(args.stop_audit),
        real_distribution_synthesis_path=str(args.real_distribution_synthesis),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_4_required_real_back_check": payload.get("v0_4_required_real_back_check")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
