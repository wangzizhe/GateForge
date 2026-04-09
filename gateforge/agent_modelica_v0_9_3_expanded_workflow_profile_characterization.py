from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_9_3_common import (
    DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR,
    DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR,
    DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH,
    NON_SUCCESS_OUTCOMES,
    SCHEMA_PREFIX,
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


def _group_distribution(rows: list[dict], group_field: str) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        grouped[str(row.get(group_field) or "")][str(row.get("pilot_outcome") or "")] += 1
    return {key: dict(counter) for key, counter in sorted(grouped.items())}


def build_v093_expanded_workflow_profile_characterization(
    *,
    replay_pack_path: str = str(DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"),
    v092_expanded_substrate_builder_path: str = str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH),
    out_dir: str = str(DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR),
) -> dict:
    replay_pack = load_json(replay_pack_path)
    builder = load_json(v092_expanded_substrate_builder_path)
    substrate_rows = {
        str(row.get("task_id") or ""): row
        for row in list(builder.get("expanded_substrate_candidate_table") or [])
    }
    case_rows_by_task = _index_case_rows_by_task_id(list(replay_pack.get("runs") or []))

    characterized_rows = []
    for task_id in sorted(case_rows_by_task):
        canonical_case = _canonical_case_row(case_rows_by_task[task_id])
        substrate_row = substrate_rows.get(task_id, {})
        characterized_rows.append(
            {
                "task_id": task_id,
                "source_id": substrate_row.get("source_id"),
                "workflow_task_template_id": substrate_row.get("workflow_task_template_id"),
                "family_id": substrate_row.get("family_id"),
                "complexity_tier": substrate_row.get("complexity_tier"),
                "goal_specific_check_mode": substrate_row.get("goal_specific_check_mode"),
                "pilot_outcome": canonical_case.get("pilot_outcome"),
                "primary_barrier_label": canonical_case.get("primary_barrier_label"),
                "expanded_substrate_membership_confirmed": bool(canonical_case.get("expanded_substrate_membership_confirmed")),
            }
        )

    total = len(characterized_rows)
    barrier_counts = Counter(
        str(row.get("primary_barrier_label") or "")
        for row in characterized_rows
        if str(row.get("pilot_outcome") or "") in NON_SUCCESS_OUTCOMES
    )
    non_success_rows = [row for row in characterized_rows if row["pilot_outcome"] in NON_SUCCESS_OUTCOMES]
    surface_rows = [row for row in characterized_rows if row["pilot_outcome"] == "surface_fix_only"]
    unresolved_rows = [row for row in characterized_rows if row["pilot_outcome"] == "unresolved"]
    barrier_covered = sum(
        1 for row in non_success_rows if str(row.get("primary_barrier_label") or "") != "profile_barrier_unclassified"
    )
    surface_explained = sum(
        1 for row in surface_rows if str(row.get("primary_barrier_label") or "") != "profile_barrier_unclassified"
    )
    unresolved_explained = sum(
        1 for row in unresolved_rows if str(row.get("primary_barrier_label") or "") != "profile_barrier_unclassified"
    )
    workflow_resolution = sum(1 for row in characterized_rows if row["pilot_outcome"] == "goal_level_resolved")
    goal_alignment = sum(1 for row in characterized_rows if row["pilot_outcome"] in {"goal_level_resolved", "surface_fix_only"})
    workflow_interpretable = bool(total) and bool(replay_pack.get("primary_workflow_route_picture_interpretable"))
    expanded_slice_interpretation = (
        f"Expanded substrate has {total} tasks, so slice summaries are no longer thin like v0.8.x, "
        "but they remain descriptive unless counts clearly support stronger claims."
    )

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_expanded_workflow_profile_characterization",
        "generated_at_utc": now_utc(),
        "status": "PASS" if workflow_interpretable else "FAIL",
        "execution_source": replay_pack.get("execution_source"),
        "profile_run_count": replay_pack.get("profile_run_count"),
        "expanded_substrate_size": total,
        "case_characterization_table": characterized_rows,
        "workflow_resolution_rate_pct": round(workflow_resolution / total * 100, 1) if total else 0.0,
        "goal_alignment_rate_pct": round(goal_alignment / total * 100, 1) if total else 0.0,
        "surface_fix_only_rate_pct": round(len(surface_rows) / total * 100, 1) if total else 0.0,
        "unresolved_rate_pct": round(len(unresolved_rows) / total * 100, 1) if total else 0.0,
        "outcome_by_workflow_task_template": _group_distribution(characterized_rows, "workflow_task_template_id"),
        "outcome_by_family_id": _group_distribution(characterized_rows, "family_id"),
        "outcome_by_complexity_tier": _group_distribution(characterized_rows, "complexity_tier"),
        "outcome_by_goal_specific_check_mode": _group_distribution(characterized_rows, "goal_specific_check_mode"),
        "barrier_label_distribution": dict(barrier_counts),
        "barrier_label_coverage_rate_pct": round(barrier_covered / len(non_success_rows) * 100, 1)
        if non_success_rows
        else 100.0,
        "surface_fix_only_explained_rate_pct": round(surface_explained / len(surface_rows) * 100, 1)
        if surface_rows
        else 100.0,
        "unresolved_explained_rate_pct": round(unresolved_explained / len(unresolved_rows) * 100, 1)
        if unresolved_rows
        else 100.0,
        "profile_barrier_unclassified_count": barrier_counts.get("profile_barrier_unclassified", 0),
        "expanded_slice_interpretation": expanded_slice_interpretation,
        "thin_slice_or_not_interpretation": "not_thin_but_still_descriptive",
        "workflow_level_interpretable": workflow_interpretable,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.9.3 Expanded Workflow Profile Characterization",
                "",
                f"- profile_run_count: `{payload['profile_run_count']}`",
                f"- workflow_resolution_rate_pct: `{payload['workflow_resolution_rate_pct']}`",
                f"- goal_alignment_rate_pct: `{payload['goal_alignment_rate_pct']}`",
                f"- barrier_label_coverage_rate_pct: `{payload['barrier_label_coverage_rate_pct']}`",
                f"- profile_barrier_unclassified_count: `{payload['profile_barrier_unclassified_count']}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.9.3 expanded workflow profile characterization.")
    parser.add_argument("--replay-pack", default=str(DEFAULT_EXPANDED_PROFILE_REPLAY_PACK_OUT_DIR / "summary.json"))
    parser.add_argument("--v092-expanded-substrate-builder", default=str(DEFAULT_V092_EXPANDED_SUBSTRATE_BUILDER_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_EXPANDED_PROFILE_CHARACTERIZATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v093_expanded_workflow_profile_characterization(
        replay_pack_path=str(args.replay_pack),
        v092_expanded_substrate_builder_path=str(args.v092_expanded_substrate_builder),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
