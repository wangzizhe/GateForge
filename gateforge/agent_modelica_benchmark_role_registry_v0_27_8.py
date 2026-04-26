from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .agent_modelica_deepseek_slice_review_v0_27_2 import load_jsonl
from .agent_modelica_generation_taxonomy_v0_19_59 import load_json


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "artifacts" / "substrate_manifest_v0_25_3" / "manifest_rows.jsonl"
DEFAULT_REPEATABILITY_SUMMARY = REPO_ROOT / "artifacts" / "single_point_family_repeatability_v0_22_9" / "summary.json"
DEFAULT_HARD_NEGATIVE_SUMMARY = REPO_ROOT / "artifacts" / "family_hard_negative_audit_v0_27_7" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "benchmark_role_registry_v0_27_8"


ROLE_CAPABILITY_BASELINE = "capability_baseline_candidate"
ROLE_HARD_NEGATIVE = "hard_negative"
ROLE_DIAGNOSTIC = "diagnostic"
ROLE_EXPLORATORY = "exploratory"


def _repeatability_by_family(summary: dict[str, Any]) -> dict[str, Counter]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for candidate in summary.get("candidate_summaries", []):
        if not isinstance(candidate, dict):
            continue
        family = str(candidate.get("mutation_family") or "")
        stability = str(candidate.get("stability") or "unknown")
        if family:
            counts[family][stability] += 1
    return dict(counts)


def _manifest_by_family(rows: list[dict[str, Any]]) -> dict[str, Counter]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        family = str(row.get("mutation_family") or "")
        split = str(row.get("split") or "unknown")
        repeatability = str(row.get("repeatability_class") or "unknown")
        if not family:
            continue
        counts[family][f"split:{split}"] += 1
        counts[family][f"repeatability:{repeatability}"] += 1
        counts[family]["total_manifest_rows"] += 1
    return dict(counts)


def _role_for_family(
    *,
    family: str,
    repeatability_counts: Counter,
    manifest_counts: Counter,
    hard_negative_summary: dict[str, Any],
) -> tuple[str, str]:
    hard_negative_family = str(hard_negative_summary.get("family") or "")
    hard_negative_decision = str(hard_negative_summary.get("decision") or "")
    if family == hard_negative_family and hard_negative_decision == "treat_family_as_current_hard_negative":
        return ROLE_HARD_NEGATIVE, "current_deepseek_audit_all_failed_with_terminal_stall"
    stable = int(repeatability_counts.get("stable_true_multi") or 0)
    unstable = int(repeatability_counts.get("unstable_true_multi") or 0)
    never = int(repeatability_counts.get("never_true_multi") or 0)
    if stable >= 2 and never == 0:
        return ROLE_CAPABILITY_BASELINE, "repeatability_gate_has_multiple_stable_true_multi_candidates"
    if stable > 0 and (never > 0 or unstable > 0):
        return ROLE_DIAGNOSTIC, "mixed_repeatability_requires_diagnostic_tracking"
    if never > 0 or int(manifest_counts.get("split:hard_negative") or 0) > 0:
        return ROLE_DIAGNOSTIC, "non_success_or_hard_negative_manifest_signal"
    return ROLE_EXPLORATORY, "insufficient_role_evidence"


def build_benchmark_role_registry(
    *,
    manifest_rows: list[dict[str, Any]],
    repeatability_summary: dict[str, Any],
    hard_negative_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    repeatability = _repeatability_by_family(repeatability_summary)
    manifest = _manifest_by_family(manifest_rows)
    families = sorted(set(repeatability) | set(manifest) | {str(hard_negative_summary.get("family") or "")})
    registry: list[dict[str, Any]] = []
    for family in families:
        if not family:
            continue
        role, rationale = _role_for_family(
            family=family,
            repeatability_counts=repeatability.get(family, Counter()),
            manifest_counts=manifest.get(family, Counter()),
            hard_negative_summary=hard_negative_summary,
        )
        registry.append(
            {
                "family": family,
                "role": role,
                "role_rationale": rationale,
                "repeatability_counts": dict(sorted(repeatability.get(family, Counter()).items())),
                "manifest_counts": dict(sorted(manifest.get(family, Counter()).items())),
                "recommended_use": _recommended_use(role),
            }
        )
    role_counts = Counter(row["role"] for row in registry)
    summary = {
        "version": "v0.27.8",
        "status": "PASS" if registry else "REVIEW",
        "analysis_scope": "benchmark_role_registry",
        "manifest_artifact": str(DEFAULT_MANIFEST.relative_to(REPO_ROOT)),
        "repeatability_artifact": str(DEFAULT_REPEATABILITY_SUMMARY.relative_to(REPO_ROOT)),
        "hard_negative_artifact": str(DEFAULT_HARD_NEGATIVE_SUMMARY.relative_to(REPO_ROOT)),
        "family_count": len(registry),
        "role_counts": dict(sorted(role_counts.items())),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "comparative_claim_made": False,
            "llm_capability_gain_claimed": False,
        },
        "decision": "benchmark_roles_ready_for_slice_selection" if registry else "benchmark_roles_need_review",
        "next_focus": "select_small_capability_and_diagnostic_slices_without_mixing_roles",
    }
    return registry, summary


def _recommended_use(role: str) -> str:
    if role == ROLE_CAPABILITY_BASELINE:
        return "small_default_capability_slice_candidate"
    if role == ROLE_HARD_NEGATIVE:
        return "hard_negative_suite_only_not_default_pass_rate"
    if role == ROLE_DIAGNOSTIC:
        return "diagnostic_suite_track_failure_modes_separately"
    return "exploratory_only"


def run_benchmark_role_registry(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    repeatability_summary_path: Path = DEFAULT_REPEATABILITY_SUMMARY,
    hard_negative_summary_path: Path = DEFAULT_HARD_NEGATIVE_SUMMARY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    registry, summary = build_benchmark_role_registry(
        manifest_rows=load_jsonl(manifest_path),
        repeatability_summary=load_json(repeatability_summary_path) if repeatability_summary_path.exists() else {},
        hard_negative_summary=load_json(hard_negative_summary_path) if hard_negative_summary_path.exists() else {},
    )
    write_outputs(out_dir=out_dir, registry=registry, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, registry: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "family_roles.jsonl").open("w", encoding="utf-8") as fh:
        for row in registry:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
