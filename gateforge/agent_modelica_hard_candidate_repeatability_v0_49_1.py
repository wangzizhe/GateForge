from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl
from .agent_modelica_hard_pool_repeatability_gate_v0_37_15 import build_repeatability_gate_summary


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEEDS = REPO_ROOT / "artifacts" / "hard_candidate_registry_promote_v0_49_0" / "registry_seeds.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_candidate_repeatability_v0_49_1"


def run_hard_candidate_repeatability_gate(
    *,
    seeds_path: Path = DEFAULT_SEEDS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, updated = build_repeatability_gate_summary(
        load_jsonl(seeds_path),
        version="v0.49.1",
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "repeatability_registry.jsonl").open("w", encoding="utf-8") as fh:
        for seed in updated:
            fh.write(json.dumps(seed, sort_keys=True) + "\n")
    return summary
