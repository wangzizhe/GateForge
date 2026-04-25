from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "runner_artifact_contract_v0_23_4"
ARTIFACT_CONTRACT_VERSION = "runner_artifact_contract_v1"
DEFAULT_RUN_SPECS = [
    {
        "run_version": "v0.23.0",
        "artifact_dir": REPO_ROOT / "artifacts" / "harness_inventory_audit_v0_23_0",
        "producer_script": "scripts/build_harness_inventory_audit_v0_23_0.py",
        "expected_files": ["file_inventory.json", "artifact_inventory.jsonl", "summary.json"],
    },
    {
        "run_version": "v0.23.1",
        "artifact_dir": REPO_ROOT / "artifacts" / "seed_registry_v0_23_1",
        "producer_script": "scripts/build_seed_registry_v0_23_1.py",
        "expected_files": ["seed_registry.jsonl", "summary.json"],
    },
    {
        "run_version": "v0.23.2",
        "artifact_dir": REPO_ROOT / "artifacts" / "trajectory_schema_v0_23_2",
        "producer_script": "scripts/build_trajectory_schema_v0_23_2.py",
        "expected_files": ["schema.json", "normalized_trajectories.jsonl", "validation_errors.jsonl", "summary.json"],
    },
    {
        "run_version": "v0.23.3",
        "artifact_dir": REPO_ROOT / "artifacts" / "oracle_contract_v0_23_3",
        "producer_script": "scripts/build_oracle_contract_v0_23_3.py",
        "expected_files": ["contract.json", "oracle_events.jsonl", "validation_errors.jsonl", "summary.json"],
    },
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def artifact_contract_definition() -> dict[str, Any]:
    return {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "required_manifest_fields": [
            "contract_version",
            "run_version",
            "artifact_dir",
            "producer_script",
            "expected_files",
            "present_files",
            "missing_files",
            "summary_status",
            "environment_metadata",
            "provider_metadata",
            "budget_metadata",
        ],
        "missing_input_policy": "return_INCOMPLETE_or_REVIEW_not_unhandled_FileNotFoundError",
        "private_path_policy": "do_not_record_absolute_private_paths",
    }


def build_artifact_manifest(spec: dict[str, Any], *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    artifact_dir = Path(spec["artifact_dir"])
    expected_files = [str(name) for name in spec.get("expected_files", [])]
    present_files = [name for name in expected_files if (artifact_dir / name).exists()]
    missing_files = [name for name in expected_files if name not in present_files]
    summary = load_json(artifact_dir / "summary.json")
    artifact_dir_text = str(artifact_dir.relative_to(repo_root)) if artifact_dir.is_relative_to(repo_root) else str(artifact_dir)
    return {
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "run_version": str(spec.get("run_version") or "unknown"),
        "artifact_dir": artifact_dir_text,
        "producer_script": str(spec.get("producer_script") or "unknown"),
        "expected_files": expected_files,
        "present_files": present_files,
        "missing_files": missing_files,
        "summary_status": str(summary.get("status") or "UNKNOWN"),
        "summary_version": str(summary.get("version") or "UNKNOWN"),
        "environment_metadata": {
            "repo_root_recorded": "relative_only",
            "requires_private_assets": False,
        },
        "provider_metadata": {
            "provider": "not_applicable_offline_harness",
            "model_profile": "not_applicable_offline_harness",
        },
        "budget_metadata": {
            "llm_calls": 0,
            "live_execution": False,
        },
    }


def validate_artifact_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in artifact_contract_definition()["required_manifest_fields"]:
        if field not in manifest:
            errors.append(f"missing:{field}")
    if manifest.get("missing_files"):
        errors.append("missing_expected_files")
    if str(manifest.get("artifact_dir") or "").startswith("/"):
        errors.append("absolute_artifact_dir_path")
    return errors


def build_runner_artifact_contract(
    *,
    run_specs: list[dict[str, Any]] | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    specs = run_specs or DEFAULT_RUN_SPECS
    manifests = [build_artifact_manifest(spec, repo_root=repo_root) for spec in specs]
    validation_errors = [
        {"run_version": manifest.get("run_version"), "errors": errors}
        for manifest in manifests
        if (errors := validate_artifact_manifest(manifest))
    ]
    status = "PASS" if manifests and not validation_errors else "REVIEW"
    summary = {
        "version": "v0.23.4",
        "status": status,
        "analysis_scope": "runner_artifact_contract_v1",
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "manifest_count": len(manifests),
        "validation_error_count": len(validation_errors),
        "contract_definition": artifact_contract_definition(),
        "discipline": {
            "executor_changes": "none",
            "deterministic_repair_added": False,
            "contract_role": "runner_artifact_shape_only",
        },
        "conclusion": (
            "runner_artifact_contract_v1_ready_for_contract_validator"
            if status == "PASS"
            else "runner_artifact_contract_v1_needs_review"
        ),
    }
    write_outputs(out_dir=out_dir, manifests=manifests, validation_errors=validation_errors, summary=summary)
    return summary


def write_outputs(
    *,
    out_dir: Path,
    manifests: list[dict[str, Any]],
    validation_errors: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "contract.json").write_text(
        json.dumps(artifact_contract_definition(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "artifact_manifests.jsonl").open("w", encoding="utf-8") as fh:
        for manifest in manifests:
            fh.write(json.dumps(manifest, sort_keys=True) + "\n")
    with (out_dir / "validation_errors.jsonl").open("w", encoding="utf-8") as fh:
        for row in validation_errors:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
