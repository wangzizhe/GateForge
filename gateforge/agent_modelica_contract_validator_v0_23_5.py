from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from gateforge.agent_modelica_oracle_contract_v0_23_3 import validate_oracle_event
from gateforge.agent_modelica_runner_artifact_contract_v0_23_4 import validate_artifact_manifest
from gateforge.agent_modelica_trajectory_schema_v0_23_2 import validate_normalized_trajectory


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUTS = {
    "seed_registry": REPO_ROOT / "artifacts" / "seed_registry_v0_23_1" / "seed_registry.jsonl",
    "trajectories": REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2" / "normalized_trajectories.jsonl",
    "oracle_events": REPO_ROOT / "artifacts" / "oracle_contract_v0_23_3" / "oracle_events.jsonl",
    "artifact_manifests": REPO_ROOT
    / "artifacts"
    / "runner_artifact_contract_v0_23_4"
    / "artifact_manifests.jsonl",
}
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "contract_validator_v0_23_5"
SEED_REQUIRED_FIELDS = (
    "seed_id",
    "candidate_id",
    "source_model",
    "mutation_family",
    "omc_admission_status",
    "live_screening_status",
    "repeatability_class",
    "registry_policy",
    "artifact_references",
    "routing_allowed",
)


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


def validate_seed_registry_row(row: dict[str, Any]) -> list[str]:
    errors = [f"missing:{field}" for field in SEED_REQUIRED_FIELDS if field not in row]
    if row.get("routing_allowed") is not False:
        errors.append("routing_allowed_must_be_false")
    if not isinstance(row.get("artifact_references"), list):
        errors.append("artifact_references_must_be_list")
    return errors


def validate_dataset(
    *,
    dataset_name: str,
    path: Path,
    validator: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    rows = load_jsonl(path)
    validation_errors = [
        {
            "dataset": dataset_name,
            "row_index": index,
            "row_id": row.get("seed_id") or row.get("case_id") or row.get("run_version") or row.get("candidate_id"),
            "errors": errors,
        }
        for index, row in enumerate(rows)
        if (errors := validator(row))
    ]
    return {
        "dataset": dataset_name,
        "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
        "row_count": len(rows),
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors,
    }


def build_contract_validation_report(
    *,
    input_paths: dict[str, Path] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    paths = input_paths or DEFAULT_INPUTS
    validators = {
        "seed_registry": validate_seed_registry_row,
        "trajectories": validate_normalized_trajectory,
        "oracle_events": validate_oracle_event,
        "artifact_manifests": validate_artifact_manifest,
    }
    reports = [
        validate_dataset(dataset_name=name, path=path, validator=validators[name])
        for name, path in paths.items()
    ]
    all_errors = [error for report in reports for error in report["validation_errors"]]
    dataset_counts = {report["dataset"]: report["row_count"] for report in reports}
    error_counts = Counter(error for item in all_errors for error in item["errors"])
    status = "PASS" if reports and all(report["row_count"] > 0 for report in reports) and not all_errors else "REVIEW"
    summary = {
        "version": "v0.23.5",
        "status": status,
        "analysis_scope": "contract_validator",
        "dataset_counts": dataset_counts,
        "dataset_validation_error_counts": {
            report["dataset"]: report["validation_error_count"] for report in reports
        },
        "total_validation_error_count": len(all_errors),
        "validation_error_type_counts": dict(sorted(error_counts.items())),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "validator_role": "contract_shape_only",
        },
        "conclusion": (
            "contract_validator_ready_for_v0_23_synthesis"
            if status == "PASS"
            else "contract_validator_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, reports=reports, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, reports: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "dataset_reports.jsonl").open("w", encoding="utf-8") as fh:
        for report in reports:
            compact = {key: value for key, value in report.items() if key != "validation_errors"}
            fh.write(json.dumps(compact, sort_keys=True) + "\n")
    with (out_dir / "validation_errors.jsonl").open("w", encoding="utf-8") as fh:
        for report in reports:
            for error in report["validation_errors"]:
                fh.write(json.dumps(error, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
