from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_pool_closeout_v0_37_12"


def build_hard_pool_closeout(
    seeds: list[dict[str, Any]],
    gate_summary: dict[str, Any],
    family_summaries: list[dict[str, Any]],
    *,
    version: str = "v0.37.12",
) -> dict[str, Any]:
    admitted = [
        seed
        for seed in seeds
        if str(seed.get("registry_status") or "") in {"admitted", "repeatable_candidate", "formal_benchmark_seed"}
    ]
    repeatable = [
        seed
        for seed in seeds
        if str(seed.get("registry_status") or "") in {"repeatable_candidate", "formal_benchmark_seed"}
    ]
    family_counts: dict[str, int] = {}
    for seed in admitted:
        family = str(seed.get("family") or "unknown")
        family_counts[family] = family_counts.get(family, 0) + 1
    return {
        "version": version,
        "analysis_scope": "hard_pool_closeout",
        "status": "PASS" if admitted else "REVIEW",
        "seed_count": len(seeds),
        "admitted_count": len(admitted),
        "repeatable_candidate_count": len(repeatable),
        "known_hard_seed_count": sum(1 for seed in seeds if seed.get("known_hard_for")),
        "family_counts": dict(sorted(family_counts.items())),
        "v0_38_ready_case_ids": [str(seed.get("case_id") or "") for seed in repeatable],
        "gate_status": gate_summary.get("status"),
        "family_summaries": family_summaries,
        "conclusion": (
            "Hard benchmark substrate is ready for difficulty calibration."
            if repeatable
            else "Hard benchmark substrate has candidates but needs repeatability evidence before v0.38."
        ),
        "scope_note": (
            "This closeout only summarizes benchmark substrate readiness. It does not claim Agent capability gains "
            "or use wrapper repair."
        ),
    }


def write_hard_pool_closeout_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

