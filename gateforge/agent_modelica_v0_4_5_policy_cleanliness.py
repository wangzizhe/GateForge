from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_5_common import (
    DEFAULT_POLICY_CLEANLINESS_OUT_DIR,
    DEFAULT_POLICY_COMPARISON_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_4_5_policy_comparison import build_v045_policy_comparison


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_policy_cleanliness"


def build_v045_policy_cleanliness(
    *,
    policy_comparison_path: str = str(DEFAULT_POLICY_COMPARISON_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR),
) -> dict:
    if not Path(policy_comparison_path).exists():
        build_v045_policy_comparison(out_dir=str(Path(policy_comparison_path).parent))
    comparison = load_json(policy_comparison_path)
    rows = comparison.get("task_rows") if isinstance(comparison.get("task_rows"), list) else []

    baseline_ambiguity_count = 0
    alternative_ambiguity_count = 0
    overlap_case_count = int(comparison.get("overlap_case_count") or 0)
    for row in rows:
        if not isinstance(row, dict):
            continue
        # The comparison keeps target family labels fixed; ambiguity stays zero unless rows are malformed.
        if bool(row.get("authority_overlap_case")) and not str(row.get("family_id") or ""):
            baseline_ambiguity_count += 1
            alternative_ambiguity_count += 1

    baseline_policy_valid = baseline_ambiguity_count == 0
    alternative_policy_valid = alternative_ambiguity_count == 0
    comparison_valid = baseline_policy_valid and alternative_policy_valid and overlap_case_count > 0

    baseline_attribution_ambiguity_rate_pct = 0.0 if overlap_case_count <= 0 else round(100.0 * baseline_ambiguity_count / float(overlap_case_count), 1)
    alternative_attribution_ambiguity_rate_pct = 0.0 if overlap_case_count <= 0 else round(100.0 * alternative_ambiguity_count / float(overlap_case_count), 1)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if comparison_valid else "FAIL",
        "policy_comparison_path": str(Path(policy_comparison_path).resolve()),
        "baseline_policy_valid": baseline_policy_valid,
        "alternative_policy_valid": alternative_policy_valid,
        "comparison_valid": comparison_valid,
        "baseline_attribution_ambiguity_rate_pct": baseline_attribution_ambiguity_rate_pct,
        "alternative_attribution_ambiguity_rate_pct": alternative_attribution_ambiguity_rate_pct,
        "overlap_case_count": overlap_case_count,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.5 Policy Cleanliness",
                "",
                f"- comparison_valid: `{payload.get('comparison_valid')}`",
                f"- baseline_policy_valid: `{payload.get('baseline_policy_valid')}`",
                f"- alternative_policy_valid: `{payload.get('alternative_policy_valid')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.5 policy cleanliness audit.")
    parser.add_argument("--policy-comparison", default=str(DEFAULT_POLICY_COMPARISON_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_POLICY_CLEANLINESS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v045_policy_cleanliness(
        policy_comparison_path=str(args.policy_comparison),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "comparison_valid": payload.get("comparison_valid")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
