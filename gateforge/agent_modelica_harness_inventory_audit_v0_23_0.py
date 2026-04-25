from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "harness_inventory_audit_v0_23_0"
VERSION_PATTERN = re.compile(r"v0_2[0-2]_\d+")
TARGET_CONTRACT_FIELDS = (
    "version",
    "status",
    "analysis_scope",
    "conclusion",
)
TRAJECTORY_HINT_FIELDS = (
    "repair_round_count",
    "feedback_sequence",
    "sample_quality",
    "executor_status",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def is_scoped_version_path(path: Path) -> bool:
    return bool(VERSION_PATTERN.search(path.as_posix()))


def discover_scoped_files(repo_root: Path) -> dict[str, list[str]]:
    scopes = {
        "modules": repo_root / "gateforge",
        "scripts": repo_root / "scripts",
        "tests": repo_root / "tests",
    }
    discovered: dict[str, list[str]] = {}
    for key, root in scopes.items():
        discovered[key] = sorted(
            str(path.relative_to(repo_root))
            for path in root.glob("*.py")
            if is_scoped_version_path(path)
        )
    return discovered


def discover_summary_paths(repo_root: Path) -> list[Path]:
    artifacts_root = repo_root / "artifacts"
    if not artifacts_root.exists():
        return []
    return sorted(
        path
        for path in artifacts_root.glob("*/summary.json")
        if is_scoped_version_path(path)
    )


def _first_case_like_row(summary: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    summaries = summary.get("summaries")
    if isinstance(summaries, list) and summaries and isinstance(summaries[0], dict):
        return summaries[0]
    for name in (
        "case_summaries.jsonl",
        "repeat_observations.jsonl",
        "case_audit.jsonl",
        "probe_rows.jsonl",
    ):
        rows = load_jsonl(artifact_dir / name)
        if rows:
            return rows[0]
    raw_dir = artifact_dir / "raw"
    if raw_dir.exists():
        for raw_path in sorted(raw_dir.glob("*.json")):
            payload = load_json(raw_path)
            if payload:
                return payload
    return {}


def classify_summary_contract(summary_path: Path, repo_root: Path) -> dict[str, Any]:
    artifact_dir = summary_path.parent
    summary = load_json(summary_path)
    keys = sorted(summary)
    missing_target_fields = [field for field in TARGET_CONTRACT_FIELDS if field not in summary]
    aggregate_only = "aggregate" in summary and "status" not in summary
    first_case = _first_case_like_row(summary, artifact_dir)
    missing_trajectory_hint_fields = [
        field for field in TRAJECTORY_HINT_FIELDS if first_case and field not in first_case
    ]
    gaps: list[str] = []
    if missing_target_fields:
        gaps.append("summary_contract_field_drift")
    if aggregate_only:
        gaps.append("aggregate_only_summary_without_top_level_status")
    if not (artifact_dir / "manifest.json").exists():
        gaps.append("missing_manifest")
    if "environment" not in summary and "environment_metadata" not in summary:
        gaps.append("missing_environment_metadata")
    if "provider" not in summary and "provider_metadata" not in summary and "model_profile" not in summary:
        gaps.append("missing_provider_metadata")
    if "budget" not in summary and "budget_metadata" not in summary:
        gaps.append("missing_budget_metadata")
    if first_case and missing_trajectory_hint_fields:
        gaps.append("trajectory_field_drift")
    return {
        "artifact": str(summary_path.relative_to(repo_root)),
        "artifact_dir": str(artifact_dir.relative_to(repo_root)),
        "summary_keys": keys,
        "has_raw_dir": (artifact_dir / "raw").exists(),
        "has_manifest": (artifact_dir / "manifest.json").exists(),
        "has_jsonl_case_rows": any(artifact_dir.glob("*.jsonl")),
        "missing_target_fields": missing_target_fields,
        "aggregate_only_summary": aggregate_only,
        "first_case_keys": sorted(first_case) if first_case else [],
        "missing_trajectory_hint_fields": missing_trajectory_hint_fields,
        "gaps": gaps,
    }


def build_gap_report(artifact_rows: list[dict[str, Any]]) -> dict[str, Any]:
    gap_counts = Counter(gap for row in artifact_rows for gap in row.get("gaps", []))
    missing_field_counts = Counter(
        field for row in artifact_rows for field in row.get("missing_target_fields", [])
    )
    return {
        "gap_counts": dict(sorted(gap_counts.items())),
        "missing_target_field_counts": dict(sorted(missing_field_counts.items())),
        "artifact_count_with_gaps": sum(1 for row in artifact_rows if row.get("gaps")),
        "artifact_count_without_gaps": sum(1 for row in artifact_rows if not row.get("gaps")),
    }


def build_harness_inventory_audit(
    *,
    repo_root: Path = REPO_ROOT,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    scoped_files = discover_scoped_files(repo_root)
    summary_paths = discover_summary_paths(repo_root)
    artifact_rows = [classify_summary_contract(path, repo_root) for path in summary_paths]
    gap_report = build_gap_report(artifact_rows)

    module_count = len(scoped_files["modules"])
    script_count = len(scoped_files["scripts"])
    test_count = len(scoped_files["tests"])
    summary_count = len(artifact_rows)
    status = "PASS" if module_count and script_count and test_count and summary_count else "INCOMPLETE"
    summary = {
        "version": "v0.23.0",
        "status": status,
        "analysis_scope": "harness_inventory_audit",
        "scanned_versions": ["v0.20.x", "v0.21.x", "v0.22.x"],
        "file_inventory": {
            "module_count": module_count,
            "script_count": script_count,
            "test_count": test_count,
            "summary_count": summary_count,
        },
        "contract_gap_report": gap_report,
        "contract_gaps_prioritized": [
            "summary_contract_field_drift",
            "missing_manifest",
            "missing_environment_metadata",
            "missing_provider_metadata",
            "missing_budget_metadata",
            "trajectory_field_drift",
            "aggregate_only_summary_without_top_level_status",
        ],
        "next_versions": {
            "v0.23.1": "seed_registry_v1",
            "v0.23.2": "trajectory_schema_v1",
            "v0.23.3": "oracle_contract_v1",
            "v0.23.4": "runner_artifact_contract_v1",
            "v0.23.5": "contract_validator",
        },
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "metric_interpretation": "harness_contract_debt_only_not_llm_capability",
        },
        "conclusion": (
            "harness_contract_gaps_identified_ready_for_v0_23_contract_freeze"
            if status == "PASS"
            else "harness_inventory_incomplete"
        ),
    }
    write_outputs(out_dir=out_dir, scoped_files=scoped_files, artifact_rows=artifact_rows, summary=summary)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    scoped_files: dict[str, list[str]],
    artifact_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "file_inventory.json").write_text(
        json.dumps(scoped_files, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "artifact_inventory.jsonl").open("w", encoding="utf-8") as fh:
        for row in artifact_rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
