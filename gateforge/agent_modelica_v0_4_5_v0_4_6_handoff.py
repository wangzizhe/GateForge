from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_5_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_POLICY_CLEANLINESS_OUT_DIR,
    DEFAULT_V0_4_6_HANDOFF_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_5_policy_adjudication import build_v045_policy_adjudication
from .agent_modelica_v0_4_5_policy_cleanliness import build_v045_policy_cleanliness


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_v0_4_6_handoff"


def build_v045_v0_4_6_handoff(
    *,
    policy_adjudication_path: str = str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"),
    policy_cleanliness_path: str = str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_V0_4_6_HANDOFF_OUT_DIR),
) -> dict:
    if not Path(policy_adjudication_path).exists():
        build_v045_policy_adjudication(out_dir=str(Path(policy_adjudication_path).parent))
    if not Path(policy_cleanliness_path).exists():
        build_v045_policy_cleanliness(out_dir=str(Path(policy_cleanliness_path).parent))
    adjudication = load_json(policy_adjudication_path)
    cleanliness = load_json(policy_cleanliness_path)

    status = str(adjudication.get("dispatch_policy_support_status") or "")
    comparison_valid = bool(cleanliness.get("comparison_valid"))
    baseline_valid = bool(cleanliness.get("baseline_policy_valid"))
    alternative_valid = bool(cleanliness.get("alternative_policy_valid"))
    alt_ambiguity = float(cleanliness.get("alternative_attribution_ambiguity_rate_pct") or 0.0)
    base_ambiguity = float(cleanliness.get("baseline_attribution_ambiguity_rate_pct") or 0.0)

    if status == "empirically_supported":
        next_step = "run_v0_4_phase_synthesis"
    elif status == "inconclusive" and baseline_valid and alternative_valid and alt_ambiguity <= base_ambiguity:
        next_step = "defer_policy_superiority_claim_and_close_phase"
    elif (not comparison_valid) or status == "not_supported":
        next_step = "run_one_more_policy_comparison"
    else:
        next_step = "defer_policy_superiority_claim_and_close_phase"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "policy_adjudication_path": str(Path(policy_adjudication_path).resolve()),
        "policy_cleanliness_path": str(Path(policy_cleanliness_path).resolve()),
        "v0_4_x_next_step": next_step,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(["# v0.4.5 -> v0.4.6 Handoff", "", f"- v0_4_x_next_step: `{next_step}`"]),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.5 -> v0.4.6 handoff.")
    parser.add_argument("--policy-adjudication", default=str(DEFAULT_ADJUDICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--policy-cleanliness", default=str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_V0_4_6_HANDOFF_OUT_DIR))
    args = parser.parse_args()
    payload = build_v045_v0_4_6_handoff(
        policy_adjudication_path=str(args.policy_adjudication),
        policy_cleanliness_path=str(args.policy_cleanliness),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "v0_4_x_next_step": payload.get("v0_4_x_next_step")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
