from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CALIBRATION = REPO_ROOT / "artifacts" / "difficulty_calibration_v0_38_4" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_core_expansion_slice_v0_39_0"

TARGET_FAMILY = "arrayed_connector_flow"
ANCHOR_CASE_IDS = {
    "sem_20_arrayed_adapter_cross_node",
    "sem_23_nested_probe_contract_bus",
    "sem_24_bridge_probe_transfer_bus",
}
PREFERRED_TERMS = (
    "arrayed",
    "probe",
    "adapter",
    "contract",
    "bus",
    "replaceable",
    "nested",
    "connector",
    "flow",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def score_expansion_candidate(row: dict[str, Any]) -> int:
    case_id = str(row.get("case_id") or "")
    if case_id in ANCHOR_CASE_IDS:
        return -1
    if str(row.get("difficulty_bucket") or "") != "needs_baseline":
        return -1
    if str(row.get("family") or "") != TARGET_FAMILY:
        return -1

    score = 0
    lowered = case_id.lower()
    for term in PREFERRED_TERMS:
        if term in lowered:
            score += 2
    if lowered.startswith("sem_"):
        score += 3
    if lowered.startswith("structural2_") or lowered.startswith("singleroot2_"):
        score += 2
    if lowered.startswith("repl_"):
        score += 1
    return score


def build_hard_core_expansion_slice(
    calibration_summary: dict[str, Any],
    *,
    limit: int = 10,
) -> dict[str, Any]:
    rows = calibration_summary.get("results") if isinstance(calibration_summary, dict) else None
    candidates = rows if isinstance(rows, list) else []
    scored = [
        (score_expansion_candidate(row), str(row.get("case_id") or ""), row)
        for row in candidates
    ]
    selected = [
        row
        for score, _, row in sorted(scored, key=lambda item: (-item[0], item[1]))
        if score >= 0
    ][:limit]
    selected_ids = [str(row.get("case_id") or "") for row in selected]
    return {
        "version": "v0.39.0",
        "analysis_scope": "hard_core_expansion_slice",
        "status": "PASS" if selected_ids else "REVIEW",
        "source_calibration_version": calibration_summary.get("version"),
        "target_family": TARGET_FAMILY,
        "anchor_case_ids": sorted(ANCHOR_CASE_IDS),
        "selection_policy": "needs_baseline_same_family_semantic_neighbor",
        "selected_case_count": len(selected_ids),
        "selected_case_ids": selected_ids,
        "runner_contract": {
            "tool_profile": "base",
            "max_steps": 10,
            "max_token_budget": 32000,
            "wrapper_repair": "forbidden",
            "provider_model_source": "environment",
        },
    }


def write_hard_core_expansion_slice_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "case_ids.txt").write_text(
        "\n".join(summary.get("selected_case_ids") or []) + "\n",
        encoding="utf-8",
    )


def run_hard_core_expansion_slice(
    *,
    calibration_path: Path = DEFAULT_CALIBRATION,
    out_dir: Path = DEFAULT_OUT_DIR,
    limit: int = 10,
) -> dict[str, Any]:
    summary = build_hard_core_expansion_slice(load_json(calibration_path), limit=limit)
    write_hard_core_expansion_slice_outputs(out_dir=out_dir, summary=summary)
    return summary

