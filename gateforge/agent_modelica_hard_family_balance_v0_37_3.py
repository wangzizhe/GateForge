from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_family_balance_v0_37_3"


def build_family_balance_summary(
    seeds: list[dict[str, Any]],
    *,
    min_family_count: int = 2,
    version: str = "v0.37.3",
) -> dict[str, Any]:
    family_counts: dict[str, int] = {}
    eligible_counts: dict[str, int] = {}
    for seed in seeds:
        family = str(seed.get("family") or "unknown")
        family_counts[family] = family_counts.get(family, 0) + 1
        if str(seed.get("registry_status") or "") in {"admitted", "repeatable_candidate", "formal_benchmark_seed"}:
            eligible_counts[family] = eligible_counts.get(family, 0) + 1
    undercovered = [
        family
        for family, count in sorted(eligible_counts.items())
        if count < int(min_family_count)
    ]
    dominant_family = ""
    if family_counts:
        dominant_family = max(family_counts.items(), key=lambda item: item[1])[0]
    dominant_share = (family_counts.get(dominant_family, 0) / len(seeds)) if seeds else 0.0
    return {
        "version": version,
        "analysis_scope": "hard_family_balance",
        "status": "PASS" if len(eligible_counts) >= 2 and dominant_share <= 0.75 else "REVIEW",
        "seed_count": len(seeds),
        "family_counts": dict(sorted(family_counts.items())),
        "eligible_family_counts": dict(sorted(eligible_counts.items())),
        "undercovered_families": undercovered,
        "dominant_family": dominant_family,
        "dominant_family_share": round(dominant_share, 4),
        "decision": (
            "family_pool_has_multiple_axes"
            if len(eligible_counts) >= 2 and dominant_share <= 0.75
            else "family_pool_needs_broader_coverage"
        ),
    }


def write_family_balance_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

