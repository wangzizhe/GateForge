from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateforge.agent_modelica_repeatability_protocol_v0_24_0 import (
    build_candidate_rows,
    build_family_rows,
    load_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_REGISTRY_PATH = REPO_ROOT / "artifacts" / "seed_registry_v0_23_1" / "seed_registry.jsonl"
DEFAULT_TRAJECTORY_PATH = REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl"
DEFAULT_EXPECTED_CANDIDATE_PATH = (
    REPO_ROOT / "artifacts" / "repeatability_protocol_v0_24_0" / "candidate_repeatability.jsonl"
)
DEFAULT_EXPECTED_FAMILY_PATH = (
    REPO_ROOT / "artifacts" / "repeatability_protocol_v0_24_0" / "family_repeatability.jsonl"
)
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "replay_harness_v0_24_5"


def _row_key(row: dict[str, Any], *, key: str) -> str:
    return str(row.get(key) or "")


def diff_rows(
    *,
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    key: str,
    fields: list[str],
) -> list[dict[str, Any]]:
    actual_by_key = {_row_key(row, key=key): row for row in actual}
    expected_by_key = {_row_key(row, key=key): row for row in expected}
    diffs: list[dict[str, Any]] = []
    for row_key in sorted(set(actual_by_key) | set(expected_by_key)):
        actual_row = actual_by_key.get(row_key)
        expected_row = expected_by_key.get(row_key)
        if actual_row is None:
            diffs.append({"key": row_key, "diff_type": "missing_actual"})
            continue
        if expected_row is None:
            diffs.append({"key": row_key, "diff_type": "missing_expected"})
            continue
        field_diffs = {
            field: {"actual": actual_row.get(field), "expected": expected_row.get(field)}
            for field in fields
            if actual_row.get(field) != expected_row.get(field)
        }
        if field_diffs:
            diffs.append({"key": row_key, "diff_type": "field_mismatch", "field_diffs": field_diffs})
    return diffs


def run_replay_harness(
    *,
    seed_registry_path: Path = DEFAULT_SEED_REGISTRY_PATH,
    trajectory_path: Path = DEFAULT_TRAJECTORY_PATH,
    expected_candidate_path: Path = DEFAULT_EXPECTED_CANDIDATE_PATH,
    expected_family_path: Path = DEFAULT_EXPECTED_FAMILY_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    seeds = load_jsonl(seed_registry_path)
    trajectories = load_jsonl(trajectory_path)
    actual_candidate_rows = build_candidate_rows(seeds=seeds, trajectories=trajectories)
    actual_family_rows = build_family_rows(actual_candidate_rows)
    expected_candidate_rows = load_jsonl(expected_candidate_path)
    expected_family_rows = load_jsonl(expected_family_path)
    missing_inputs = []
    for name, rows in (
        ("seed_registry", seeds),
        ("trajectories", trajectories),
        ("expected_candidate_repeatability", expected_candidate_rows),
        ("expected_family_repeatability", expected_family_rows),
    ):
        if not rows:
            missing_inputs.append(name)

    candidate_diffs = diff_rows(
        actual=actual_candidate_rows,
        expected=expected_candidate_rows,
        key="candidate_id",
        fields=["repeatability_class", "observation_count", "trajectory_class_counts"],
    )
    family_diffs = diff_rows(
        actual=actual_family_rows,
        expected=expected_family_rows,
        key="mutation_family",
        fields=["family_repeatability_class", "candidate_repeatability_counts", "candidate_count"],
    )
    status = "PASS" if not missing_inputs and not candidate_diffs and not family_diffs else "REVIEW"
    summary = {
        "version": "v0.24.5",
        "status": status,
        "analysis_scope": "replay_harness",
        "seed_count": len(seeds),
        "trajectory_count": len(trajectories),
        "candidate_count": len(actual_candidate_rows),
        "family_count": len(actual_family_rows),
        "missing_inputs": missing_inputs,
        "candidate_diff_count": len(candidate_diffs),
        "family_diff_count": len(family_diffs),
        "replay_policy": "recompute_classification_without_model_calls_or_history_repair",
        "discipline": {
            "executor_changes": "none",
            "llm_calls": 0,
            "deterministic_repair_added": False,
            "replay_can_recompute_but_not_rewrite_history": True,
        },
        "conclusion": (
            "replay_harness_ready_for_v0_24_synthesis"
            if status == "PASS"
            else "replay_harness_needs_review"
        ),
    }
    write_outputs(
        out_dir=out_dir,
        candidate_rows=actual_candidate_rows,
        family_rows=actual_family_rows,
        candidate_diffs=candidate_diffs,
        family_diffs=family_diffs,
        summary=summary,
    )
    return summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def write_outputs(
    *,
    out_dir: Path,
    candidate_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    candidate_diffs: list[dict[str, Any]],
    family_diffs: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "replayed_candidate_repeatability.jsonl", candidate_rows)
    _write_jsonl(out_dir / "replayed_family_repeatability.jsonl", family_rows)
    _write_jsonl(out_dir / "candidate_diffs.jsonl", candidate_diffs)
    _write_jsonl(out_dir / "family_diffs.jsonl", family_diffs)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
