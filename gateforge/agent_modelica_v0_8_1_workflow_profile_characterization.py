from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_8_1_common import (
    DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V080_SUBSTRATE_PATH,
    SCHEMA_PREFIX,
    goal_specific_check_mode,
    load_json,
    now_utc,
    outcome_sort_key,
    write_json,
    write_text,
)


def _index_case_rows_by_task_id(runs: list[dict]) -> dict[str, list[dict]]:
    indexed: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        for row in list(run.get("case_result_table") or []):
            task_id = str(row.get("task_id") or "")
            if task_id:
                indexed[task_id].append(row)
    return indexed


def _canonical_case_row(rows: list[dict]) -> dict:
    if not rows:
        return {}
    ordered = sorted(
        rows,
        key=lambda row: (
            outcome_sort_key(str(row.get("pilot_outcome") or "")),
            str(row.get("task_id") or ""),
        ),
    )
    outcome_counts = Counter(str(row.get("pilot_outcome") or "") for row in rows)
    canonical_outcome = sorted(
        outcome_counts.items(),
        key=lambda item: (-item[1], outcome_sort_key(item[0]), item[0]),
    )[0][0]
    for row in rows:
        if str(row.get("pilot_outcome") or "") == canonical_outcome:
            return row
    return ordered[0]


def derive_primary_barrier_label(case_row: dict, substrate_row: dict) -> str:
    outcome = str(case_row.get("pilot_outcome") or "")
    legacy_bucket = str(case_row.get("legacy_bucket_after_live_run") or "")
    checks = list(substrate_row.get("workflow_acceptance_checks") or [])
    acceptance_results = case_row.get("acceptance_check_results") or {}
    failed_check_types = [
        str(check.get("type") or "")
        for index, check in enumerate(checks, start=1)
        if not bool(acceptance_results.get(f"{index}:{str(check.get('type') or '')}", False))
    ]
    workflow_only_failed_types = [
        check_type
        for check_type in failed_check_types
        if check_type in {"named_result_invariant_pass", "expected_goal_artifact_present"}
    ]

    if outcome == "surface_fix_only" and "expected_goal_artifact_present" in workflow_only_failed_types:
        return "goal_artifact_missing_after_surface_fix"
    if outcome == "surface_fix_only" and "named_result_invariant_pass" in workflow_only_failed_types:
        return "goal_invariant_failed_after_surface_fix"
    if outcome == "unresolved" and legacy_bucket == "dispatch_or_policy_limited":
        return "dispatch_or_policy_limited_unresolved"
    if outcome == "unresolved" and legacy_bucket == "topology_or_open_world_spillover":
        return "workflow_spillover_unresolved"
    if outcome == "unresolved" and legacy_bucket in {"covered_success", "covered_but_fragile"}:
        return "dispatch_or_policy_limited_unresolved"
    if outcome == "goal_misaligned":
        return "goal_context_not_satisfied_despite_surface_fix"
    return "profile_barrier_unclassified"


def _group_distribution(rows: list[dict], group_field: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get(group_field) or "")][str(row.get("pilot_outcome") or "")] += 1
    return {key: dict(counter) for key, counter in sorted(grouped.items())}


def _group_barrier_distribution(rows: list[dict], group_field: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get(group_field) or "")][str(row.get("primary_barrier_label") or "")] += 1
    return {key: dict(counter) for key, counter in sorted(grouped.items())}


def build_v081_workflow_profile_characterization(
    *,
    replay_pack_path: str = str(DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    substrate_path: str = str(DEFAULT_V080_SUBSTRATE_PATH),
    out_dir: str = str(DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR),
) -> dict:
    replay_pack = load_json(replay_pack_path)
    substrate = load_json(substrate_path)
    substrate_rows = {
        str(row.get("task_id") or ""): row for row in list(substrate.get("task_rows") or [])
    }
    case_rows_by_task = _index_case_rows_by_task_id(list(replay_pack.get("runs") or []))

    characterized_rows = []
    for task_id in sorted(case_rows_by_task):
        canonical_case = _canonical_case_row(case_rows_by_task[task_id])
        substrate_row = substrate_rows.get(task_id, {})
        barrier_label = derive_primary_barrier_label(canonical_case, substrate_row)
        checks = list(substrate_row.get("workflow_acceptance_checks") or [])
        mode = goal_specific_check_mode(checks)
        characterized_rows.append(
            {
                "task_id": task_id,
                "pilot_outcome": canonical_case.get("pilot_outcome"),
                "primary_barrier_label": barrier_label,
                "legacy_bucket_after_live_run": canonical_case.get("legacy_bucket_after_live_run"),
                "workflow_task_template_id": substrate_row.get("workflow_task_template_id"),
                "family_id": substrate_row.get("family_id"),
                "complexity_tier": substrate_row.get("complexity_tier"),
                "goal_specific_check_mode": mode,
                "workflow_only_goal_check_required": mode != "none",
            }
        )

    barrier_counts = Counter(
        row["primary_barrier_label"]
        for row in characterized_rows
        if row["pilot_outcome"] != "goal_level_resolved"
    )
    non_success_rows = [row for row in characterized_rows if row["pilot_outcome"] != "goal_level_resolved"]
    surface_rows = [row for row in characterized_rows if row["pilot_outcome"] == "surface_fix_only"]
    unresolved_rows = [row for row in characterized_rows if row["pilot_outcome"] == "unresolved"]
    barrier_covered = sum(
        1 for row in non_success_rows if row["primary_barrier_label"] != "profile_barrier_unclassified"
    )
    surface_explained = sum(
        1 for row in surface_rows if row["primary_barrier_label"] != "profile_barrier_unclassified"
    )
    unresolved_explained = sum(
        1 for row in unresolved_rows if row["primary_barrier_label"] != "profile_barrier_unclassified"
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_workflow_profile_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "execution_source": "gateforge_run_contract_live_path",
        "profile_run_count": replay_pack.get("profile_run_count"),
        "case_characterization_table": characterized_rows,
        "outcome_by_workflow_task_template": _group_distribution(
            characterized_rows, "workflow_task_template_id"
        ),
        "outcome_by_family_id": _group_distribution(characterized_rows, "family_id"),
        "outcome_by_complexity_tier": _group_distribution(characterized_rows, "complexity_tier"),
        "outcome_by_goal_specific_check_mode": _group_distribution(
            characterized_rows, "goal_specific_check_mode"
        ),
        "barrier_label_distribution": dict(barrier_counts),
        "barrier_label_distribution_by_slice": {
            "workflow_task_template_id": _group_barrier_distribution(
                [row for row in characterized_rows if row["pilot_outcome"] != "goal_level_resolved"],
                "workflow_task_template_id",
            ),
            "goal_specific_check_mode": _group_barrier_distribution(
                [row for row in characterized_rows if row["pilot_outcome"] != "goal_level_resolved"],
                "goal_specific_check_mode",
            ),
        },
        "legacy_bucket_crosswalk_by_outcome": {
            outcome: dict(
                Counter(
                    str(row.get("legacy_bucket_after_live_run") or "")
                    for row in characterized_rows
                    if row["pilot_outcome"] == outcome
                )
            )
            for outcome in sorted({row["pilot_outcome"] for row in characterized_rows}, key=outcome_sort_key)
        },
        "goal_context_dependency_case_count": sum(
            1 for row in characterized_rows if bool(row["workflow_only_goal_check_required"])
        ),
        "barrier_label_coverage_rate_pct": round(
            barrier_covered / len(non_success_rows) * 100, 1
        )
        if non_success_rows
        else 100.0,
        "surface_fix_only_explained_rate_pct": round(
            surface_explained / len(surface_rows) * 100, 1
        )
        if surface_rows
        else 100.0,
        "unresolved_explained_rate_pct": round(
            unresolved_explained / len(unresolved_rows) * 100, 1
        )
        if unresolved_rows
        else 100.0,
        "profile_barrier_unclassified_count": barrier_counts.get("profile_barrier_unclassified", 0),
        "thin_slice_warning": "Most slices are descriptive only because the frozen substrate has 10 tasks.",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.8.1 Workflow Profile Characterization",
                "",
                f"- profile_run_count: `{payload['profile_run_count']}`",
                f"- barrier_label_coverage_rate_pct: `{payload['barrier_label_coverage_rate_pct']}`",
                f"- surface_fix_only_explained_rate_pct: `{payload['surface_fix_only_explained_rate_pct']}`",
                f"- unresolved_explained_rate_pct: `{payload['unresolved_explained_rate_pct']}`",
                f"- profile_barrier_unclassified_count: `{payload['profile_barrier_unclassified_count']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.8.1 workflow profile characterization.")
    parser.add_argument(
        "--replay-pack-path",
        default=str(DEFAULT_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--substrate-path", default=str(DEFAULT_V080_SUBSTRATE_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v081_workflow_profile_characterization(
        replay_pack_path=str(args.replay_pack_path),
        substrate_path=str(args.substrate_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
