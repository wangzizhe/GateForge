from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_pool_evidence_reconcile_v0_37_13"


def reconcile_seed_evidence(seed: dict[str, Any]) -> dict[str, Any]:
    reconciled = dict(seed)
    known_hard_for = [str(item) for item in seed.get("known_hard_for") or [] if str(item).strip()]
    evidence_count = len(known_hard_for)
    if evidence_count and str(reconciled.get("admission_status") or "") == "not_run":
        reconciled["admission_status"] = "admitted_via_live_failure"
    if evidence_count >= 2 and str(reconciled.get("repeatability_status") or "") == "not_run":
        reconciled["repeatability_status"] = "repeatability_evidence_present"
    elif evidence_count and str(reconciled.get("repeatability_status") or "") == "not_run":
        reconciled["repeatability_status"] = "repeatability_pending"
    if evidence_count:
        reconciled["evidence_role"] = "formal_experiment"
    if str(reconciled.get("registry_status") or "") == "candidate" and evidence_count:
        reconciled["registry_status"] = "admitted"
    reconciled["known_hard_evidence_count"] = evidence_count
    return reconciled


def build_evidence_reconcile_summary(
    seeds: list[dict[str, Any]],
    *,
    version: str = "v0.37.13",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reconciled = [reconcile_seed_evidence(seed) for seed in seeds]
    status_counts: dict[str, int] = {}
    repeatability_counts: dict[str, int] = {}
    for seed in reconciled:
        status = str(seed.get("admission_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        repeatability = str(seed.get("repeatability_status") or "unknown")
        repeatability_counts[repeatability] = repeatability_counts.get(repeatability, 0) + 1
    evidence_case_ids = [
        str(seed.get("case_id") or "")
        for seed in reconciled
        if int(seed.get("known_hard_evidence_count") or 0) > 0
    ]
    return (
        {
            "version": version,
            "analysis_scope": "hard_pool_evidence_reconcile",
            "status": "PASS" if evidence_case_ids else "REVIEW",
            "seed_count": len(seeds),
            "known_hard_seed_count": len(evidence_case_ids),
            "admission_status_counts": dict(sorted(status_counts.items())),
            "repeatability_status_counts": dict(sorted(repeatability_counts.items())),
            "known_hard_case_ids": evidence_case_ids,
            "scope_note": (
                "Known-hard evidence can admit a case as a live failure substrate. It does not automatically make "
                "the case a repeatable formal benchmark seed unless repeatability evidence is explicit."
            ),
        },
        reconciled,
    )


def write_evidence_reconcile_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    seeds: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "reconciled_registry.jsonl").open("w", encoding="utf-8") as fh:
        for seed in seeds:
            fh.write(json.dumps(seed, sort_keys=True) + "\n")

