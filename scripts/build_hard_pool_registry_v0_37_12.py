#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_candidate_intake_v0_37_1 import build_candidate_intake_summary
from gateforge.agent_modelica_hard_family_balance_v0_37_3 import build_family_balance_summary
from gateforge.agent_modelica_hard_family_expansion_v0_37_4 import (
    build_arrayed_connector_flow_expansion_summary,
)
from gateforge.agent_modelica_hard_family_expansion_v0_37_7 import (
    build_replaceable_partial_expansion_summary,
)
from gateforge.agent_modelica_hard_family_expansion_v0_37_10 import (
    build_reusable_contract_expansion_summary,
)
from gateforge.agent_modelica_hard_family_registry_v0_37_0 import build_registry_summary
from gateforge.agent_modelica_hard_pool_closeout_v0_37_12 import build_hard_pool_closeout
from gateforge.agent_modelica_hard_pool_evidence_reconcile_v0_37_13 import (
    build_evidence_reconcile_summary,
)
from gateforge.agent_modelica_hard_pool_gate_v0_37_2 import build_hard_pool_gate_summary
from gateforge.agent_modelica_hard_pool_leakage_triage_v0_37_14 import (
    build_leakage_triage_summary,
)
from gateforge.agent_modelica_hard_pool_repeatability_gate_v0_37_15 import (
    build_repeatability_gate_summary,
)
from gateforge.agent_modelica_known_hard_artifact_miner_v0_37_1 import mine_known_hard_from_artifacts

DEFAULT_TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks" / "repair"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_pool_registry_v0_37_12"


def load_tasks(task_root: Path) -> list[dict[str, Any]]:
    paths = [task_root] if task_root.is_file() else sorted(task_root.rglob("*.json"))
    tasks: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            payload.setdefault("source_reference", str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path))
            tasks.append(payload)
    return tasks


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.37 hard benchmark substrate registry.")
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--artifact-summary",
        type=Path,
        action="append",
        default=[],
        help="Existing summary.json artifact used to populate known_hard_for.",
    )
    args = parser.parse_args()

    tasks = load_tasks(args.task_root)
    known_hard = mine_known_hard_from_artifacts(args.artifact_summary)
    intake_summary, seeds = build_candidate_intake_summary(tasks, known_hard_by_case=known_hard)

    evidence_summary, reconciled_seeds = build_evidence_reconcile_summary(seeds)
    repeatability_summary, repeatable_seeds = build_repeatability_gate_summary(reconciled_seeds)
    registry_summary = build_registry_summary(repeatable_seeds)
    gate_summary = build_hard_pool_gate_summary(repeatable_seeds)
    leakage_summary = build_leakage_triage_summary(repeatable_seeds)
    balance_summary = build_family_balance_summary(repeatable_seeds)
    family_summaries = [
        build_arrayed_connector_flow_expansion_summary(repeatable_seeds),
        build_replaceable_partial_expansion_summary(repeatable_seeds),
        build_reusable_contract_expansion_summary(repeatable_seeds),
    ]
    closeout_summary = build_hard_pool_closeout(repeatable_seeds, gate_summary, family_summaries)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "summary.json", closeout_summary)
    write_json(args.out_dir / "intake_summary.json", intake_summary)
    write_json(args.out_dir / "evidence_reconcile_summary.json", evidence_summary)
    write_json(args.out_dir / "repeatability_gate_summary.json", repeatability_summary)
    write_json(args.out_dir / "registry_summary.json", registry_summary)
    write_json(args.out_dir / "gate_summary.json", gate_summary)
    write_json(args.out_dir / "leakage_triage_summary.json", leakage_summary)
    write_json(args.out_dir / "balance_summary.json", balance_summary)
    write_json(args.out_dir / "family_summaries.json", {"family_summaries": family_summaries})
    write_json(args.out_dir / "known_hard_map.json", known_hard)
    write_jsonl(args.out_dir / "registry.jsonl", repeatable_seeds)
    print(json.dumps({"status": closeout_summary["status"], "seed_count": len(repeatable_seeds)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
