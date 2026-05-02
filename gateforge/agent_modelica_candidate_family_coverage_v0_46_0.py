from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = REPO_ROOT / "artifacts" / "semantic_candidate_generation_policy_probe_v0_45_2" / "results.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "candidate_family_coverage_v0_46_0"

TARGET_CASE_IDS = {
    "sem_06_repl_array_flow",
    "sem_13_arrayed_connector_bus_refactor",
    "sem_26_three_segment_adapter_cross_node",
    "singleroot2_02_replaceable_probe_array",
}

CANDIDATE_FAMILY_TERMS = {
    "symmetric_zero_current": ("p.i = 0", "n.i = 0", "all adapter currents", "all pins"),
    "pair_flow_contract": ("p.i + n.i", "high[i].i + low[i].i", "through-variable"),
    "base_contract_move": ("probebase", "adapterbase", "base class", "partial"),
    "implementation_contract_move": ("voltprobe", "voltageadapter", "branchprobe", "implementation"),
    "topology_rewrite": ("different topology", "connection pattern", "connect(", "same node"),
    "loop_unroll": ("unroll", "for loop"),
    "standard_library_sensor": ("voltagesensor", "standard"),
    "compiler_limitation_exit": ("compiler", "matching algorithm", "known omc issue"),
}


def _step_text(row: dict[str, Any]) -> str:
    return "\n".join(str(step.get("text") or "") for step in row.get("steps") or [])


def detect_candidate_families(row: dict[str, Any]) -> list[str]:
    text = _step_text(row).lower()
    families: list[str] = []
    for family, terms in CANDIDATE_FAMILY_TERMS.items():
        if any(term.lower() in text for term in terms):
            families.append(family)
    return families


def build_candidate_family_coverage(
    rows: list[dict[str, Any]],
    *,
    version: str = "v0.46.0",
) -> dict[str, Any]:
    audited = []
    family_counts: dict[str, int] = {}
    missing_family_counts: dict[str, int] = {}
    for row in rows:
        case_id = str(row.get("case_id") or "")
        if case_id not in TARGET_CASE_IDS:
            continue
        families = detect_candidate_families(row)
        missing = sorted(set(CANDIDATE_FAMILY_TERMS) - set(families))
        for family in families:
            family_counts[family] = family_counts.get(family, 0) + 1
        for family in missing:
            missing_family_counts[family] = missing_family_counts.get(family, 0) + 1
        audited.append(
            {
                "case_id": case_id,
                "final_verdict": str(row.get("final_verdict") or ""),
                "submitted": bool(row.get("submitted")),
                "detected_candidate_families": families,
                "missing_candidate_families": missing,
            }
        )
    return {
        "version": version,
        "analysis_scope": "candidate_family_coverage",
        "status": "PASS" if audited else "REVIEW",
        "case_count": len(audited),
        "target_case_ids": sorted(TARGET_CASE_IDS),
        "family_counts": dict(sorted(family_counts.items())),
        "missing_family_counts": dict(sorted(missing_family_counts.items())),
        "results": sorted(audited, key=lambda item: item["case_id"]),
        "decision": "test_uncovered_candidate_families",
        "scope_note": (
            "This audit describes candidate-family coverage from LLM text. It does not decide which candidate is "
            "correct, generate patches, route cases, or submit."
        ),
    }


def write_candidate_family_coverage_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_candidate_family_coverage(
    *,
    results_path: Path = DEFAULT_RESULTS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary = build_candidate_family_coverage(load_jsonl(results_path))
    write_candidate_family_coverage_outputs(out_dir=out_dir, summary=summary)
    return summary

