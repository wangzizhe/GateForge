"""Block B: Dispatch Cleanliness + Auditability Gate for v0.6.0.

Evaluates whether the representative substrate has clean enough dispatch
attribution to support the authority admission pipeline.

Ambiguity rule: a case is marked ambiguous if its slice_class is
boundary-adjacent or undeclared-but-bounded-candidate AND its
qualitative_bucket involves cross-domain interface pressure where
the dominant_stage_subtype cannot cleanly distinguish family origin.
Already-covered cases are never ambiguous (their attribution is
validated by the v0.5.x authority chain).
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path
from typing import Any

from .agent_modelica_v0_6_0_common import (
    DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
    DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    DISPATCH_CLEANLINESS_DEGRADED_THRESHOLD,
    DISPATCH_CLEANLINESS_PROMOTED_THRESHOLD,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)

# Cases whose qualitative_bucket creates genuine cross-family dispatch
# ambiguity are those involving cross_domain_interface_pressure at complex
# tier; medium-tier cross_domain cases remain locally interpretable.
_AMBIGUOUS_QUALITATIVE_BUCKETS = {"cross_domain_interface_pressure"}
_AMBIGUOUS_TIERS_FOR_CROSS_DOMAIN = {"complex"}


def _is_ambiguous(case: dict[str, Any]) -> bool:
    if case["slice_class"] == "already-covered":
        return False
    bucket = case.get("qualitative_bucket", "none")
    tier = case.get("complexity_tier", "simple")
    if bucket in _AMBIGUOUS_QUALITATIVE_BUCKETS and tier in _AMBIGUOUS_TIERS_FOR_CROSS_DOMAIN:
        return True
    return False


def _cleanliness_level(ambiguity_rate_pct: float) -> str:
    if ambiguity_rate_pct <= DISPATCH_CLEANLINESS_PROMOTED_THRESHOLD:
        return "promoted"
    if ambiguity_rate_pct <= DISPATCH_CLEANLINESS_DEGRADED_THRESHOLD:
        return "degraded_but_executable"
    return "failed"


def build_dispatch_cleanliness(
    substrate_dir: Path = DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR,
    out_dir: Path = DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR,
) -> dict[str, Any]:
    substrate = load_json(substrate_dir / "summary.json")
    assert substrate.get("representative_slice_frozen"), (
        "Block A must have frozen the representative substrate first"
    )

    cases: list[dict[str, Any]] = substrate["task_rows"]
    n = len(cases)

    ambiguous_cases = [c for c in cases if _is_ambiguous(c)]
    clean_cases = [c for c in cases if not _is_ambiguous(c)]
    ambiguity_rate_pct = round(len(ambiguous_cases) / n * 100, 1)
    cleanliness_level = _cleanliness_level(ambiguity_rate_pct)
    policy_baseline_valid = cleanliness_level != "failed"
    classification_auditability_ready = policy_baseline_valid

    ambiguous_task_ids = [c["task_id"] for c in ambiguous_cases]

    result: dict[str, Any] = {
        "schema_version": f"{SCHEMA_PREFIX}_dispatch_cleanliness",
        "generated_at_utc": now_utc(),
        "status": "PASS" if policy_baseline_valid else "FAIL",
        "case_count": n,
        "clean_case_count": len(clean_cases),
        "ambiguous_case_count": len(ambiguous_cases),
        "attribution_ambiguity_rate_pct": ambiguity_rate_pct,
        "dispatch_cleanliness_level": cleanliness_level,
        "policy_baseline_valid": policy_baseline_valid,
        "classification_auditability_ready": classification_auditability_ready,
        "ambiguity_rule": (
            "A case is ambiguous when: (a) slice_class is boundary-adjacent "
            "or undeclared-but-bounded-candidate, AND (b) qualitative_bucket "
            "is cross_domain_interface_pressure, AND (c) complexity_tier is "
            "complex. Already-covered cases are never ambiguous."
        ),
        "ambiguous_task_ids": ambiguous_task_ids,
        "threshold_promoted": DISPATCH_CLEANLINESS_PROMOTED_THRESHOLD,
        "threshold_degraded": DISPATCH_CLEANLINESS_DEGRADED_THRESHOLD,
        "gate_decision": (
            "PASS — dispatch attribution is auditable; v0.6.0 may proceed "
            "to Block C."
            if policy_baseline_valid
            else "FAIL — dispatch attribution too ambiguous; v0.6.0 must "
            "collect representative_substrate_invalid."
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", result)

    md = textwrap.dedent(f"""
        # Block B: Dispatch Cleanliness Gate — v0.6.0

        **Status**: {result['status']}
        **Ambiguity rate**: {ambiguity_rate_pct}% ({len(ambiguous_cases)}/{n} cases)
        **Cleanliness level**: {cleanliness_level}
        **Policy baseline valid**: {policy_baseline_valid}
        **Auditability ready**: {classification_auditability_ready}

        ## Ambiguous cases
        {ambiguous_task_ids or 'none'}

        ## Gate decision
        {result['gate_decision']}
    """).strip()
    write_text(out_dir / "summary.md", md)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Block B: v0.6.0 dispatch cleanliness gate"
    )
    parser.add_argument(
        "--substrate-dir", type=Path, default=DEFAULT_REPRESENTATIVE_SUBSTRATE_OUT_DIR
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_DISPATCH_CLEANLINESS_OUT_DIR)
    args = parser.parse_args()

    result = build_dispatch_cleanliness(
        substrate_dir=args.substrate_dir,
        out_dir=args.out_dir,
    )
    print(
        f"[Block B] status={result['status']}  "
        f"ambiguity={result['attribution_ambiguity_rate_pct']}%  "
        f"level={result['dispatch_cleanliness_level']}"
    )


if __name__ == "__main__":
    main()
