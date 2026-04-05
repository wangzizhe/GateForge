from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_5_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_POLICY_CLEANLINESS_OUT_DIR,
    DEFAULT_POLICY_COMPARISON_OUT_DIR,
    DEFAULT_SLICE_LOCK_OUT_DIR,
    DEFAULT_V0_4_6_HANDOFF_OUT_DIR,
    DEFAULT_V043_CLOSEOUT_PATH,
    DEFAULT_V044_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_5_policy_adjudication import build_v045_policy_adjudication
from .agent_modelica_v0_4_5_policy_cleanliness import build_v045_policy_cleanliness
from .agent_modelica_v0_4_5_policy_comparison import build_v045_policy_comparison
from .agent_modelica_v0_4_5_policy_slice_lock import build_v045_policy_slice_lock
from .agent_modelica_v0_4_5_v0_4_6_handoff import build_v045_v0_4_6_handoff


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v045_closeout(
    *,
    v0_4_3_closeout_path: str = str(DEFAULT_V043_CLOSEOUT_PATH),
    v0_4_4_closeout_path: str = str(DEFAULT_V044_CLOSEOUT_PATH),
    policy_slice_lock_path: str = str(DEFAULT_SLICE_LOCK_OUT_DIR / "summary.json"),
    policy_comparison_path: str = str(DEFAULT_POLICY_COMPARISON_OUT_DIR / "summary.json"),
    policy_cleanliness_path: str = str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR / "summary.json"),
    policy_adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    v0_4_6_handoff_path: str = str(DEFAULT_V0_4_6_HANDOFF_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(policy_slice_lock_path).exists():
        build_v045_policy_slice_lock(out_dir=str(Path(policy_slice_lock_path).parent))
    if not Path(policy_comparison_path).exists():
        build_v045_policy_comparison(out_dir=str(Path(policy_comparison_path).parent))
    if not Path(policy_cleanliness_path).exists():
        build_v045_policy_cleanliness(out_dir=str(Path(policy_cleanliness_path).parent))
    if not Path(policy_adjudication_path).exists():
        build_v045_policy_adjudication(out_dir=str(Path(policy_adjudication_path).parent))
    if not Path(v0_4_6_handoff_path).exists():
        build_v045_v0_4_6_handoff(out_dir=str(Path(v0_4_6_handoff_path).parent))

    v043 = load_json(v0_4_3_closeout_path)
    v044 = load_json(v0_4_4_closeout_path)
    slice_lock = load_json(policy_slice_lock_path)
    comparison = load_json(policy_comparison_path)
    cleanliness = load_json(policy_cleanliness_path)
    adjudication = load_json(policy_adjudication_path)
    handoff = load_json(v0_4_6_handoff_path)

    support_status = str(adjudication.get("dispatch_policy_support_status") or "")
    comparison_valid = bool(cleanliness.get("comparison_valid"))
    if not bool(slice_lock.get("policy_comparison_slice_locked")):
        version_decision = "v0_4_5_policy_comparison_invalid"
        primary_bottleneck = "policy_slice_not_locked"
    elif not comparison_valid:
        version_decision = "v0_4_5_policy_comparison_invalid"
        primary_bottleneck = "comparison_validity_failed"
    elif support_status == "empirically_supported":
        version_decision = "v0_4_5_dispatch_policy_empirically_supported"
        primary_bottleneck = "none"
    elif support_status == "not_supported":
        version_decision = "v0_4_5_dispatch_policy_not_supported"
        primary_bottleneck = "baseline_policy_outperformed"
    else:
        version_decision = "v0_4_5_dispatch_policy_inconclusive"
        primary_bottleneck = "no_clear_policy_advantage"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "V0_4_5_DISPATCH_POLICY_COMPARISON",
        "conclusion": {
            "version_decision": version_decision,
            "dispatch_policy_support_status": support_status,
            "comparison_valid": comparison_valid,
            "primary_bottleneck": primary_bottleneck,
            "v0_4_x_next_step": handoff.get("v0_4_x_next_step"),
        },
        "v0_4_3_closeout": v043,
        "v0_4_4_closeout": v044,
        "policy_slice_lock": slice_lock,
        "policy_comparison": comparison,
        "policy_cleanliness": cleanliness,
        "policy_adjudication": adjudication,
        "v0_4_6_handoff": handoff,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.5 Closeout",
                "",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- dispatch_policy_support_status: `{(payload.get('conclusion') or {}).get('dispatch_policy_support_status')}`",
                f"- v0_4_x_next_step: `{(payload.get('conclusion') or {}).get('v0_4_x_next_step')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.5 closeout.")
    parser.add_argument("--v0-4-3-closeout", default=str(DEFAULT_V043_CLOSEOUT_PATH))
    parser.add_argument("--v0-4-4-closeout", default=str(DEFAULT_V044_CLOSEOUT_PATH))
    parser.add_argument("--policy-slice-lock", default=str(DEFAULT_SLICE_LOCK_OUT_DIR / "summary.json"))
    parser.add_argument("--policy-comparison", default=str(DEFAULT_POLICY_COMPARISON_OUT_DIR / "summary.json"))
    parser.add_argument("--policy-cleanliness", default=str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR / "summary.json"))
    parser.add_argument("--policy-adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--v0-4-6-handoff", default=str(DEFAULT_V0_4_6_HANDOFF_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v045_closeout(
        v0_4_3_closeout_path=str(args.v0_4_3_closeout),
        v0_4_4_closeout_path=str(args.v0_4_4_closeout),
        policy_slice_lock_path=str(args.policy_slice_lock),
        policy_comparison_path=str(args.policy_comparison),
        policy_cleanliness_path=str(args.policy_cleanliness),
        policy_adjudication_path=str(args.policy_adjudication),
        v0_4_6_handoff_path=str(args.v0_4_6_handoff),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
