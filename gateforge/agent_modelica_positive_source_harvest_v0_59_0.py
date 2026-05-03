from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HARD_PACK = REPO_ROOT / "artifacts" / "hard_benchmark_pack_v0_49_2" / "summary.json"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts"
DEFAULT_REFERENCE_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "reference_repairs"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "positive_source_harvest_v0_59_0"


def discover_result_paths(artifact_root: Path = DEFAULT_ARTIFACT_ROOT) -> list[Path]:
    if not artifact_root.exists():
        return []
    return sorted(artifact_root.glob("*/results.jsonl"))


def discover_reference_repair_paths(reference_root: Path = DEFAULT_REFERENCE_ROOT) -> dict[str, list[str]]:
    if not reference_root.exists():
        return {}
    out: dict[str, list[str]] = {}
    for path in sorted(reference_root.glob("**/*.json")):
        case_id = path.stem
        out.setdefault(case_id, []).append(str(path))
    return out


def harvest_successful_trajectories(*, hard_case_ids: list[str], result_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    hard = set(hard_case_ids)
    out: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in hard_case_ids}
    for path in result_paths:
        for row in load_jsonl(path):
            case_id = str(row.get("case_id") or "")
            if case_id not in hard:
                continue
            if str(row.get("provider_error") or "").strip():
                continue
            if str(row.get("final_verdict") or "").upper() != "PASS":
                continue
            if not bool(row.get("submitted")):
                continue
            out[case_id].append(
                {
                    "source_type": "successful_repaired_trajectory",
                    "source_path": str(path),
                    "tool_profile": str(row.get("tool_profile") or ""),
                    "run_mode": str(row.get("run_mode") or ""),
                    "submitted": True,
                    "has_final_model_text": bool(str(row.get("final_model_text") or "").strip()),
                }
            )
    return {case_id: rows for case_id, rows in out.items() if rows}


def build_positive_source_harvest(
    *,
    hard_pack_summary: dict[str, Any],
    result_paths: list[Path],
    reference_paths_by_case: dict[str, list[str]],
    version: str = "v0.59.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hard_case_ids = sorted(str(case_id) for case_id in hard_pack_summary.get("hard_case_ids") or [])
    successes = harvest_successful_trajectories(hard_case_ids=hard_case_ids, result_paths=result_paths)
    records: list[dict[str, Any]] = []
    for case_id in hard_case_ids:
        for source_path in reference_paths_by_case.get(case_id, []):
            records.append(
                {
                    "case_id": case_id,
                    "source_type": "private_reference_repair",
                    "source_path": source_path,
                    "prompt_visible": False,
                    "may_train_after_label_gate": True,
                }
            )
        for source in successes.get(case_id, []):
            records.append(
                {
                    "case_id": case_id,
                    **source,
                    "prompt_visible": False,
                    "may_train_after_label_gate": True,
                }
            )
    covered = sorted({record["case_id"] for record in records})
    missing = sorted(case_id for case_id in hard_case_ids if case_id not in set(covered))
    counts_by_type: dict[str, int] = {}
    for record in records:
        source_type = str(record["source_type"])
        counts_by_type[source_type] = counts_by_type.get(source_type, 0) + 1
    summary = {
        "version": version,
        "analysis_scope": "positive_source_harvest",
        "status": "REVIEW" if missing else "PASS",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "positive_sources_partial" if missing else "positive_sources_complete",
        "hard_case_count": len(hard_case_ids),
        "positive_source_case_count": len(covered),
        "missing_positive_source_count": len(missing),
        "positive_source_record_count": len(records),
        "source_type_counts": dict(sorted(counts_by_type.items())),
        "positive_source_case_ids": covered,
        "missing_positive_source_case_ids": missing,
        "prompt_visibility_contract": {
            "positive_sources_enter_agent_prompt": False,
            "reference_repairs_enter_external_bundle": False,
            "successful_trajectory_paths_are_audit_only": True,
        },
        "next_actions": [
            "create_or_validate_reference_repairs_for_missing_cases",
            "run_label_gate_before_training_use",
            "keep_positive_sources_hidden_from_live_agent",
        ],
    }
    return summary, sorted(records, key=lambda row: (row["case_id"], row["source_type"], row["source_path"]))


def write_positive_source_harvest_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    records: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "positive_sources.jsonl").open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    (out_dir / "missing_positive_source_case_ids.txt").write_text(
        "\n".join(summary["missing_positive_source_case_ids"]) + ("\n" if summary["missing_positive_source_case_ids"] else ""),
        encoding="utf-8",
    )


def run_positive_source_harvest(
    *,
    hard_pack_path: Path = DEFAULT_HARD_PACK,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    reference_root: Path = DEFAULT_REFERENCE_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    summary, records = build_positive_source_harvest(
        hard_pack_summary=load_json(hard_pack_path),
        result_paths=discover_result_paths(artifact_root),
        reference_paths_by_case=discover_reference_repair_paths(reference_root),
    )
    write_positive_source_harvest_outputs(out_dir=out_dir, summary=summary, records=records)
    return summary
