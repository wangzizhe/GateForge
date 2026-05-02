from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK = REPO_ROOT / "artifacts" / "hard_benchmark_pack_v0_49_2" / "summary.json"
DEFAULT_PROMOTION = REPO_ROOT / "artifacts" / "hard_candidate_registry_promote_v0_49_0" / "summary.json"
DEFAULT_REPEATABILITY = REPO_ROOT / "artifacts" / "hard_candidate_repeatability_v0_49_1" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_benchmark_closeout_v0_49_4"


def build_hard_benchmark_closeout(
    *,
    pack: dict[str, Any],
    promotion: dict[str, Any],
    repeatability: dict[str, Any],
    version: str = "v0.49.4",
) -> dict[str, Any]:
    return {
        "version": version,
        "analysis_scope": "hard_benchmark_closeout",
        "status": "PASS" if pack.get("status") == "PASS" else "REVIEW",
        "evidence_role": "formal_experiment",
        "conclusion_allowed": bool(pack.get("conclusion_allowed")),
        "promoted_seed_count": int(promotion.get("promoted_seed_count") or 0),
        "repeatability_pass_count": int(repeatability.get("repeatability_pass_count") or 0),
        "hard_pack_count": int(pack.get("hard_pack_count") or 0),
        "new_hard_count": int(pack.get("new_hard_count") or 0),
        "unstable_case_count": len(pack.get("unstable_case_ids") or []),
        "easy_calibration_case_count": len(pack.get("easy_calibration_case_ids") or []),
        "decision": "v0_49_benchmark_pack_ready",
        "next_options": [
            "continue_expanding_around_sem_32",
            "run_external_agent_comparison_on_hard_pack",
            "fill_positive_supervision_labels",
        ],
    }


def run_hard_benchmark_closeout(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    summary = build_hard_benchmark_closeout(
        pack=load_json(DEFAULT_PACK),
        promotion=load_json(DEFAULT_PROMOTION),
        repeatability=load_json(DEFAULT_REPEATABILITY),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
