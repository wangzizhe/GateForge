from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_benchmark_blind_gate_v0_36_4 import lint_benchmark_blindness


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_pool_leakage_triage_v0_37_14"


def triage_seed_leakage(seed: dict[str, Any]) -> dict[str, Any]:
    lint = lint_benchmark_blindness(
        {
            "case_id": seed.get("case_id"),
            "description": seed.get("visible_task_description"),
            "constraints": seed.get("visible_constraints") or [],
        }
    )
    action = "keep"
    if lint["status"] != "PASS":
        action = "rewrite_prompt_or_reject"
    return {
        "case_id": str(seed.get("case_id") or ""),
        "family": str(seed.get("family") or ""),
        "status": lint["status"],
        "recommended_action": action,
        "hit_count": lint["leakage_risk_count"],
        "hits": lint["hits"],
    }


def build_leakage_triage_summary(
    seeds: list[dict[str, Any]],
    *,
    version: str = "v0.37.14",
) -> dict[str, Any]:
    rows = [triage_seed_leakage(seed) for seed in seeds]
    leaking = [row for row in rows if row["status"] != "PASS"]
    return {
        "version": version,
        "analysis_scope": "hard_pool_leakage_triage",
        "status": "PASS" if not leaking else "REVIEW",
        "seed_count": len(seeds),
        "leaking_seed_count": len(leaking),
        "leaking_case_ids": [row["case_id"] for row in leaking],
        "results": rows,
    }


def write_leakage_triage_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
