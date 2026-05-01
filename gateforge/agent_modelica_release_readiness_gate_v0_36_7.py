from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "release_readiness_gate_v0_36_7"

READINESS_CHECKS = [
    "provider_stable",
    "base_tool_use_sanity_passed",
    "artifact_complete",
    "repair_report_readable",
    "failure_modes_distinguished",
    "benchmark_blind",
    "no_wrapper_repair",
]


def evaluate_release_readiness(
    checks: dict[str, bool],
    *,
    version: str = "v0.36.7",
) -> dict[str, Any]:
    rows = [
        {"check": name, "passed": bool(checks.get(name, False))}
        for name in READINESS_CHECKS
    ]
    failed = [row["check"] for row in rows if not row["passed"]]
    return {
        "version": version,
        "analysis_scope": "gateforge_agent_release_readiness",
        "status": "PASS" if not failed else "REVIEW",
        "readiness_status": "readiness_complete" if not failed else "readiness_incomplete",
        "conclusion_allowed": not failed,
        "failed_checks": failed,
        "checks": rows,
    }


def write_release_readiness_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

