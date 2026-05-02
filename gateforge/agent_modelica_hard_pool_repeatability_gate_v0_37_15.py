from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "hard_pool_repeatability_gate_v0_37_15"


def _profile_key(descriptor: str) -> str:
    parts = [part.strip() for part in str(descriptor or "").split("/")]
    if len(parts) >= 4:
        return " / ".join(parts[:4])
    return str(descriptor or "").strip()


def evaluate_repeatability(seed: dict[str, Any], *, min_evidence_count: int = 2) -> dict[str, Any]:
    known_hard_for = [str(item) for item in seed.get("known_hard_for") or [] if str(item).strip()]
    profile_counts: dict[str, int] = {}
    for descriptor in known_hard_for:
        key = _profile_key(descriptor)
        profile_counts[key] = profile_counts.get(key, 0) + 1
    repeated_profiles = {
        profile: count
        for profile, count in sorted(profile_counts.items())
        if count >= int(min_evidence_count)
    }
    repeatability_status = "repeatability_pending"
    if repeated_profiles:
        repeatability_status = "repeatable_known_hard"
    elif len(known_hard_for) >= int(min_evidence_count):
        repeatability_status = "cross_profile_hard_evidence"
    elif not known_hard_for:
        repeatability_status = "no_known_hard_evidence"
    return {
        "case_id": str(seed.get("case_id") or ""),
        "family": str(seed.get("family") or ""),
        "known_hard_evidence_count": len(known_hard_for),
        "profile_counts": dict(sorted(profile_counts.items())),
        "repeated_profiles": repeated_profiles,
        "repeatability_status": repeatability_status,
        "formal_repeatability_passed": repeatability_status == "repeatable_known_hard",
    }


def apply_repeatability_gate(
    seeds: list[dict[str, Any]],
    *,
    min_evidence_count: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for seed in seeds:
        row = evaluate_repeatability(seed, min_evidence_count=min_evidence_count)
        rows.append(row)
        next_seed = dict(seed)
        if row["formal_repeatability_passed"]:
            next_seed["repeatability_status"] = "repeatable"
            if str(next_seed.get("registry_status") or "") in {"admitted", "repeatable_candidate"}:
                next_seed["registry_status"] = "repeatable_candidate"
        elif row["repeatability_status"] == "cross_profile_hard_evidence":
            next_seed["repeatability_status"] = "repeatability_cross_profile_only"
        updated.append(next_seed)
    return updated, rows


def build_repeatability_gate_summary(
    seeds: list[dict[str, Any]],
    *,
    min_evidence_count: int = 2,
    version: str = "v0.37.15",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated, rows = apply_repeatability_gate(seeds, min_evidence_count=min_evidence_count)
    passed = [row for row in rows if row["formal_repeatability_passed"]]
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("repeatability_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "version": version,
        "analysis_scope": "hard_pool_repeatability_gate",
        "status": "PASS" if passed else "REVIEW",
        "seed_count": len(seeds),
        "repeatability_pass_count": len(passed),
        "repeatability_status_counts": dict(sorted(status_counts.items())),
        "repeatable_case_ids": [row["case_id"] for row in passed],
        "min_evidence_count": int(min_evidence_count),
        "scope_note": (
            "This gate promotes only repeated known-hard evidence under the same provider/model/profile/budget key. "
            "Cross-profile hard evidence is useful difficulty prior, but not formal repeatability."
        ),
        "results": rows,
    }
    return summary, updated


def write_repeatability_gate_outputs(
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
    with (out_dir / "repeatability_registry.jsonl").open("w", encoding="utf-8") as fh:
        for seed in seeds:
            fh.write(json.dumps(seed, sort_keys=True) + "\n")

