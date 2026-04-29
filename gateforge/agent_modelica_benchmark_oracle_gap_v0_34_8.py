from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASK_PATH = (
    REPO_ROOT
    / "assets_private"
    / "benchmarks"
    / "agent_comparison_v1"
    / "tasks"
    / "repair"
    / "sem_19_arrayed_shared_probe_bus.json"
)
DEFAULT_BOUNDARY_ATTRIBUTION = REPO_ROOT / "artifacts" / "semantic_memory_boundary_attribution_v0_34_7" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_oracle_gap_v0_34_8"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _constraint_flags(task: dict[str, Any]) -> dict[str, bool]:
    text = " ".join(str(item) for item in task.get("constraints", [])).lower()
    description = str(task.get("description") or "").lower()
    joined = f"{description} {text}"
    return {
        "mentions_reusable_contract": "reusable" in joined or "contract" in joined,
        "mentions_replaceable_interface": "replaceable" in joined,
        "mentions_required_readings": "reading" in joined or "measurement" in joined,
        "mentions_topology_preservation": "topology" in joined,
    }


def _verification_flags(task: dict[str, Any]) -> dict[str, bool]:
    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    return {
        "has_check_model": bool(verification.get("check_model")),
        "has_simulate": isinstance(verification.get("simulate"), dict),
        "has_behavioral_contract_oracle": isinstance(verification.get("behavioral"), dict)
        or isinstance(verification.get("contract"), dict),
    }


def build_benchmark_oracle_gap(
    *,
    task_path: Path = DEFAULT_TASK_PATH,
    boundary_attribution_path: Path = DEFAULT_BOUNDARY_ATTRIBUTION,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    task = load_json(task_path)
    attribution = load_json(boundary_attribution_path)
    constraint_flags = _constraint_flags(task)
    verification_flags = _verification_flags(task)
    reusable_concern_seen = int(attribution.get("reusable_contract_concern_count") or 0) > 0
    oracle_gap = (
        constraint_flags["mentions_reusable_contract"]
        and reusable_concern_seen
        and not verification_flags["has_behavioral_contract_oracle"]
    )
    summary = {
        "version": "v0.34.8",
        "status": "PASS" if task and attribution else "REVIEW",
        "analysis_scope": "benchmark_oracle_gap",
        "task_loaded": bool(task),
        "boundary_attribution_loaded": bool(attribution),
        "constraint_flags": constraint_flags,
        "verification_flags": verification_flags,
        "reusable_contract_concern_seen": reusable_concern_seen,
        "oracle_gap_detected": oracle_gap,
        "decision": "benchmark_oracle_needs_contract_semantics" if oracle_gap else "benchmark_oracle_gap_not_established",
        "discipline": {
            "oracle_audit_only": True,
            "deterministic_repair_added": False,
            "candidate_selection_added": False,
            "auto_submit_added": False,
            "wrapper_patch_generated": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
