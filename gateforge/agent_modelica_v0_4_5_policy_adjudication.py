from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_5_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_POLICY_CLEANLINESS_OUT_DIR,
    DEFAULT_POLICY_COMPARISON_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_5_policy_cleanliness import build_v045_policy_cleanliness
from .agent_modelica_v0_4_5_policy_comparison import build_v045_policy_comparison


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_policy_adjudication"


def build_v045_policy_adjudication(
    *,
    policy_comparison_path: str = str(DEFAULT_POLICY_COMPARISON_OUT_DIR / "summary.json"),
    policy_cleanliness_path: str = str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(policy_comparison_path).exists():
        build_v045_policy_comparison(out_dir=str(Path(policy_comparison_path).parent))
    if not Path(policy_cleanliness_path).exists():
        build_v045_policy_cleanliness(out_dir=str(Path(policy_cleanliness_path).parent))
    comparison = load_json(policy_comparison_path)
    cleanliness = load_json(policy_cleanliness_path)

    comparison_valid = bool(cleanliness.get("comparison_valid"))
    gain_delta = float(comparison.get("policy_gain_delta_pct") or 0.0)
    signature_delta = float(comparison.get("policy_signature_delta_pct") or 0.0)
    overlap_delta = float(comparison.get("baseline_overlap_resolution_rate_pct") or 0.0) - float(comparison.get("alternative_overlap_resolution_rate_pct") or 0.0)

    if not comparison_valid:
        support_status = "invalid"
        support_basis = "invalid_comparison"
        quant = {}
    elif gain_delta > 0:
        support_status = "empirically_supported"
        support_basis = "higher_real_success"
        quant = {"policy_gain_delta_pct": gain_delta}
    elif signature_delta > 0:
        support_status = "empirically_supported"
        support_basis = "higher_signature_advance"
        quant = {"policy_signature_delta_pct": signature_delta}
    elif overlap_delta > 0:
        support_status = "empirically_supported"
        support_basis = "cleaner_overlap_resolution"
        quant = {"overlap_resolution_delta_pct": round(overlap_delta, 1)}
    elif gain_delta < 0 or signature_delta < 0 or overlap_delta < 0:
        support_status = "not_supported"
        support_basis = "alternative_policy_advantage"
        quant = {
            "policy_gain_delta_pct": gain_delta,
            "policy_signature_delta_pct": signature_delta,
            "overlap_resolution_delta_pct": round(overlap_delta, 1),
        }
    else:
        support_status = "inconclusive"
        support_basis = "no_clear_advantage"
        quant = {
            "policy_gain_delta_pct": gain_delta,
            "policy_signature_delta_pct": signature_delta,
            "overlap_resolution_delta_pct": round(overlap_delta, 1),
        }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if support_status != "invalid" else "FAIL",
        "policy_comparison_path": str(Path(policy_comparison_path).resolve()),
        "policy_cleanliness_path": str(Path(policy_cleanliness_path).resolve()),
        "dispatch_policy_support_status": support_status,
        "support_basis": support_basis,
        "support_basis_quantitative_support": quant,
        "comparison_valid": comparison_valid,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.5 Policy Adjudication",
                "",
                f"- dispatch_policy_support_status: `{payload.get('dispatch_policy_support_status')}`",
                f"- support_basis: `{payload.get('support_basis')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.5 policy adjudication.")
    parser.add_argument("--policy-comparison", default=str(DEFAULT_POLICY_COMPARISON_OUT_DIR / "summary.json"))
    parser.add_argument("--policy-cleanliness", default=str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v045_policy_adjudication(
        policy_comparison_path=str(args.policy_comparison),
        policy_cleanliness_path=str(args.policy_cleanliness),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "dispatch_policy_support_status": payload.get("dispatch_policy_support_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
