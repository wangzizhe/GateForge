from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "evidence_role_contract_v0_36_3"

EVIDENCE_ROLES = {
    "formal_experiment",
    "smoke",
    "debug",
    "abandoned_exploration",
}


def compute_conclusion_allowed(
    *,
    evidence_role: str,
    provider_status: str,
    provider_error_count: int,
    load_error_count: int,
    artifact_complete: bool,
) -> bool:
    return (
        evidence_role == "formal_experiment"
        and provider_status == "provider_stable"
        and int(provider_error_count) == 0
        and int(load_error_count) == 0
        and bool(artifact_complete)
    )


def apply_evidence_contract(
    summary: dict[str, Any],
    *,
    evidence_role: str,
    provider_status: str = "provider_stable",
    provider_error_count: int = 0,
    load_error_count: int = 0,
    artifact_complete: bool = True,
) -> dict[str, Any]:
    if evidence_role not in EVIDENCE_ROLES:
        raise ValueError(f"unknown evidence_role: {evidence_role}")
    normalized = dict(summary)
    normalized.update(
        {
            "evidence_role": evidence_role,
            "provider_status": provider_status,
            "provider_error_count": int(provider_error_count),
            "load_error_count": int(load_error_count),
            "artifact_complete": bool(artifact_complete),
            "conclusion_allowed": compute_conclusion_allowed(
                evidence_role=evidence_role,
                provider_status=provider_status,
                provider_error_count=provider_error_count,
                load_error_count=load_error_count,
                artifact_complete=artifact_complete,
            ),
        }
    )
    return normalized


def write_evidence_contract_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

