from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_0_conditioning_reactivation_audit import build_v040_conditioning_reactivation_audit
from .agent_modelica_v0_4_0_synthetic_baseline import build_v040_synthetic_baseline
from .agent_modelica_v0_4_0_common import (
    DEFAULT_CONDITIONING_AUDIT_OUT_DIR,
    DEFAULT_SYNTHETIC_BASELINE_OUT_DIR,
    DEFAULT_V0_4_1_HANDOFF_OUT_DIR,
    DEFAULT_V0334_HANDOFF_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_1_handoff"


def build_v040_v0_4_1_handoff(
    *,
    conditioning_audit_path: str = str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR / "summary.json"),
    synthetic_baseline_path: str = str(DEFAULT_SYNTHETIC_BASELINE_OUT_DIR / "summary.json"),
    v0334_handoff_path: str = str(DEFAULT_V0334_HANDOFF_PATH),
    out_dir: str = str(DEFAULT_V0_4_1_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(conditioning_audit_path).exists():
        build_v040_conditioning_reactivation_audit(out_dir=str(Path(conditioning_audit_path).parent))
    if not Path(synthetic_baseline_path).exists():
        build_v040_synthetic_baseline(
            conditioning_audit_path=conditioning_audit_path,
            out_dir=str(Path(synthetic_baseline_path).parent),
        )

    audit = load_json(conditioning_audit_path)
    baseline = load_json(synthetic_baseline_path)
    legacy = load_json(v0334_handoff_path)

    if bool(audit.get("conditioning_reactivation_ready")):
        primary_eval_question = "Does curriculum conditioning improve three-family synthetic repair outcomes, and does that movement survive a targeted real-distribution back-check?"
        policy_eval_scope = "targeted_policy_sidecar_after_real_back_check"
        next_phase_recommendation = "run_real_back_check_then_policy_eval"
    else:
        primary_eval_question = "How do we refresh or rebuild stage_2-aligned conditioning signal on the three-family curriculum before real back-check and policy evaluation?"
        policy_eval_scope = "dispatch_policy_frozen_but_not_yet_compared"
        next_phase_recommendation = "repair_stage2_conditioning_signal_then_run_real_back_check"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "conditioning_audit_path": str(Path(conditioning_audit_path).resolve()),
        "synthetic_baseline_path": str(Path(synthetic_baseline_path).resolve()),
        "v0334_handoff_path": str(Path(v0334_handoff_path).resolve()),
        "v0_4_1_primary_eval_question": primary_eval_question,
        "v0_4_1_required_real_back_check": True,
        "v0_4_1_policy_eval_scope": policy_eval_scope,
        "v0_4_1_conditioning_followup": str(audit.get("primary_bottleneck") or "none"),
        "next_phase_recommendation": next_phase_recommendation,
        "v0_4_multi_family_policy_requirement": legacy.get("v0_4_multi_family_policy_requirement") or {},
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.0 v0.4.1 Handoff",
                "",
                f"- next_phase_recommendation: `{payload.get('next_phase_recommendation')}`",
                f"- v0_4_1_required_real_back_check: `{payload.get('v0_4_1_required_real_back_check')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.0 -> v0.4.1 handoff.")
    parser.add_argument("--conditioning-audit", default=str(DEFAULT_CONDITIONING_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--synthetic-baseline", default=str(DEFAULT_SYNTHETIC_BASELINE_OUT_DIR / "summary.json"))
    parser.add_argument("--v0334-handoff", default=str(DEFAULT_V0334_HANDOFF_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_1_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v040_v0_4_1_handoff(
        conditioning_audit_path=str(args.conditioning_audit),
        synthetic_baseline_path=str(args.synthetic_baseline),
        v0334_handoff_path=str(args.v0334_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "next_phase_recommendation": payload.get("next_phase_recommendation")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
