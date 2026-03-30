from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_layer4_generation_priority_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_layer4_generation_priority_v0_3_2"
DEFAULT_FAMILY_SPEC = "artifacts/agent_modelica_layer4_family_spec_v0_3_0/spec.json"
DEFAULT_HARD_LANE_SUMMARY = "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/summary.json"
DEFAULT_EXPANSION_SUMMARY = "artifacts/agent_modelica_planner_sensitive_expansion_v0_3_2/summary.json"
DEFAULT_EXPANSION_TASKSET = "artifacts/agent_modelica_planner_sensitive_expansion_v0_3_2/taskset_candidates.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else payload.get("cases")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _family_rows(payload: dict) -> list[dict]:
    rows = payload.get("families")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _family_id_for_candidate(row: dict) -> str:
    return _norm(row.get("v0_3_family_id"))


def _family_id_for_excluded_row(row: dict) -> str:
    failure_type = _norm(row.get("failure_type")).lower()
    if failure_type == "initialization_infeasible":
        return "initialization_singularity"
    if failure_type == "solver_sensitive_simulate_failure":
        return "runtime_numerical_instability"
    return "hard_multiround_simulate_failure"


def _reason_count(rows: list[dict], reason: str) -> int:
    out = 0
    for row in rows:
        reasons = row.get("selection_reasons") if isinstance(row.get("selection_reasons"), list) else []
        if reason in reasons:
            out += 1
    return out


def _family_note_list(family_row: dict) -> list[str]:
    notes = family_row.get("notes")
    if not isinstance(notes, list):
        return []
    return [_norm(item) for item in notes if _norm(item)]


def _family_plan(
    *,
    family_row: dict,
    hard_lane_row: dict,
    candidate_rows: list[dict],
    excluded_rows: list[dict],
) -> dict:
    family_id = _norm(family_row.get("family_id"))
    family_label = _norm(family_row.get("display_name") or family_id)
    proxy_rows = [row for row in candidate_rows if _norm(row.get("classification")) == "proxy_candidate"]
    freeze_ready_rows = [row for row in candidate_rows if _norm(row.get("classification")) == "freeze_ready_observed"]

    proxy_count = len(proxy_rows)
    freeze_ready_count = len(freeze_ready_rows)
    excluded_easy_count = len(excluded_rows)

    source_not_yet_solved_count = _reason_count(proxy_rows, "source_result_not_yet_solved")
    source_multi_round_count = _reason_count(proxy_rows, "source_result_multi_round")
    expected_multi_round_count = _reason_count(proxy_rows, "expected_multi_round")
    simulate_phase_required_count = _reason_count(proxy_rows, "simulate_phase_required")
    cascade_depth_count = _reason_count(proxy_rows, "cascade_depth_ge_2")
    mock_success_round_count = _reason_count(proxy_rows, "mock_success_round_ge_2")
    no_direct_outcome_count = _reason_count(proxy_rows, "no_direct_outcome_available")

    priority_score = 0
    priority_score += proxy_count * 3
    priority_score += freeze_ready_count * 6
    priority_score += source_not_yet_solved_count * 4
    priority_score += source_multi_round_count * 5
    priority_score += expected_multi_round_count * 3
    priority_score += simulate_phase_required_count * 2
    priority_score += cascade_depth_count * 2
    priority_score += mock_success_round_count * 2
    priority_score += no_direct_outcome_count
    if expected_multi_round_count > 0 and simulate_phase_required_count > 0:
        priority_score += 6
    if source_not_yet_solved_count > 0 and cascade_depth_count > 0:
        priority_score += 4
    if proxy_count > 0 and source_not_yet_solved_count <= 0 and source_multi_round_count <= 0 and expected_multi_round_count <= 0:
        priority_score -= 4
    if (
        proxy_count > 0
        and source_multi_round_count <= 0
        and expected_multi_round_count <= 0
        and simulate_phase_required_count <= 0
        and cascade_depth_count <= 0
        and mock_success_round_count <= 0
    ):
        priority_score -= 12
    if excluded_easy_count > proxy_count and proxy_count > 0:
        priority_score -= 2

    priority_bucket = "priority_3_backlog"
    if priority_score >= 18:
        priority_bucket = "priority_1_generate_now"
    elif priority_score >= 10:
        priority_bucket = "priority_2_generate_after_p1"
    if (
        proxy_count > 0
        and source_multi_round_count <= 0
        and expected_multi_round_count <= 0
        and simulate_phase_required_count <= 0
        and cascade_depth_count <= 0
        and mock_success_round_count <= 0
        and priority_bucket == "priority_1_generate_now"
    ):
        priority_bucket = "priority_2_generate_after_p1"

    rationales: list[str] = []
    if source_not_yet_solved_count > 0:
        rationales.append(f"`{source_not_yet_solved_count}` proxy candidates are not yet solved by GateForge in source evidence.")
    if source_multi_round_count > 0:
        rationales.append(f"`{source_multi_round_count}` proxy candidates already show multi-round source outcomes.")
    if expected_multi_round_count > 0:
        rationales.append(f"`{expected_multi_round_count}` proxy candidates explicitly encode expected multi-round behavior.")
    if simulate_phase_required_count > 0:
        rationales.append(f"`{simulate_phase_required_count}` proxy candidates require simulate-phase diagnostics.")
    if cascade_depth_count > 0:
        rationales.append(f"`{cascade_depth_count}` proxy candidates expose cascade depth >= 2.")
    if excluded_easy_count > 0:
        rationales.append(f"`{excluded_easy_count}` already-observed tasks from this family were excluded as easy proxies.")
    if not rationales:
        rationales.append("Current evidence is too weak to justify near-term generation priority.")

    generation_axes = []
    generation_axes.extend(_family_note_list(family_row))
    if family_id == "hard_multiround_simulate_failure":
        generation_axes.append("prioritize coupled-conflict or cascading mutations that preserve simulate-pass after the first local fix")
    elif family_id == "runtime_numerical_instability":
        generation_axes.append("push solver-sensitive dynamics toward reproducible multi-round repair rather than single-pass numeric fixes")
    elif family_id == "initialization_singularity":
        generation_axes.append("target initialization conflicts that remain simulate-stage failures after non-planner patches")

    family_support_count = int(hard_lane_row.get("task_count") or 0)
    gateforge_success_rate_pct = float(hard_lane_row.get("gateforge_success_rate_pct") or 0.0)
    return {
        "family_id": family_id,
        "family_label": family_label,
        "priority_score": int(priority_score),
        "priority_bucket": priority_bucket,
        "current_proxy_count": proxy_count,
        "current_freeze_ready_count": freeze_ready_count,
        "excluded_easy_count": excluded_easy_count,
        "family_support_count": family_support_count,
        "gateforge_success_rate_pct": gateforge_success_rate_pct,
        "signal_counts": {
            "source_result_not_yet_solved": source_not_yet_solved_count,
            "source_result_multi_round": source_multi_round_count,
            "expected_multi_round": expected_multi_round_count,
            "simulate_phase_required": simulate_phase_required_count,
            "cascade_depth_ge_2": cascade_depth_count,
            "mock_success_round_ge_2": mock_success_round_count,
            "no_direct_outcome_available": no_direct_outcome_count,
        },
        "rationales": rationales,
        "generation_axes": generation_axes,
    }


def _observed_reference_families(candidate_rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in candidate_rows:
        if _norm(row.get("classification")) != "freeze_ready_observed":
            continue
        family_id = _norm(row.get("multi_step_family") or row.get("failure_type"))
        if not family_id:
            continue
        grouped.setdefault(family_id, []).append(row)
    rows: list[dict] = []
    for family_id in sorted(grouped.keys()):
        items = grouped[family_id]
        decisive_count = _reason_count(items, "planner_decisive_observed")
        rows.append(
            {
                "family_id": family_id,
                "observed_freeze_ready_count": len(items),
                "planner_decisive_count": decisive_count,
                "role": "reference_seed_only",
                "note": "preserve as the observed planner-sensitive seed lane; do not treat as the harder Layer 4 family taxonomy",
            }
        )
    return rows


def _allocate_recommended_counts(family_plans: list[dict], freeze_ready_gap: int) -> list[dict]:
    active = [row for row in family_plans if _norm(row.get("priority_bucket")) != "priority_3_backlog"]
    total_score = sum(max(1, int(row.get("priority_score") or 0)) for row in active)
    remaining = max(0, int(freeze_ready_gap))
    for row in family_plans:
        row["recommended_new_task_target"] = 0
    if remaining <= 0 or total_score <= 0:
        return family_plans

    allocated = 0
    for index, row in enumerate(active):
        score = max(1, int(row.get("priority_score") or 0))
        target = max(1, round((score / total_score) * remaining))
        if index == len(active) - 1:
            target = max(1, remaining - allocated)
        row["recommended_new_task_target"] = int(target)
        allocated += int(target)
    return family_plans


def build_generation_priority(
    *,
    family_spec_path: str = DEFAULT_FAMILY_SPEC,
    hard_lane_summary_path: str = DEFAULT_HARD_LANE_SUMMARY,
    expansion_summary_path: str = DEFAULT_EXPANSION_SUMMARY,
    expansion_taskset_path: str = DEFAULT_EXPANSION_TASKSET,
) -> dict:
    family_spec = _load_json(family_spec_path)
    hard_lane_summary = _load_json(hard_lane_summary_path)
    expansion_summary = _load_json(expansion_summary_path)
    expansion_taskset = _load_json(expansion_taskset_path)

    family_rows = [row for row in _family_rows(family_spec) if bool(row.get("enabled_for_v0_3_0"))]
    hard_lane_by_family = {
        _norm(row.get("family_id")): row
        for row in (hard_lane_summary.get("family_summaries") or [])
        if isinstance(row, dict) and _norm(row.get("family_id"))
    }
    candidate_rows = _task_rows(expansion_taskset)
    excluded_rows = [
        row for row in (expansion_summary.get("excluded_rows") or []) if isinstance(row, dict)
    ]

    target_freeze_ready_count = int(expansion_summary.get("target_freeze_ready_count") or 0)
    freeze_ready_count = int(expansion_summary.get("freeze_ready_count") or 0)
    freeze_ready_gap = max(0, target_freeze_ready_count - freeze_ready_count)

    family_plans: list[dict] = []
    for family_row in family_rows:
        family_id = _norm(family_row.get("family_id"))
        plan = _family_plan(
            family_row=family_row,
            hard_lane_row=hard_lane_by_family.get(family_id, {}),
            candidate_rows=[row for row in candidate_rows if _family_id_for_candidate(row) == family_id],
            excluded_rows=[row for row in excluded_rows if _family_id_for_excluded_row(row) == family_id],
        )
        family_plans.append(plan)

    family_plans.sort(key=lambda row: (-int(row.get("priority_score") or 0), _norm(row.get("family_id"))))
    family_plans = _allocate_recommended_counts(family_plans, freeze_ready_gap)

    priority_now = [row for row in family_plans if _norm(row.get("priority_bucket")) == "priority_1_generate_now"]
    priority_next = [row for row in family_plans if _norm(row.get("priority_bucket")) == "priority_2_generate_after_p1"]
    backlog = [row for row in family_plans if _norm(row.get("priority_bucket")) == "priority_3_backlog"]

    status = "PASS" if freeze_ready_gap <= 0 else "NEEDS_GENERATION_EXECUTION"
    next_actions = []
    if priority_now:
        next_actions.append("Generate the priority_1 families first and rerun planner-sensitive expansion before freezing Track C.")
    if priority_next:
        next_actions.append("Use priority_2 families only after checking whether the priority_1 rerun materially increased freeze-ready observed cases.")
    if backlog:
        next_actions.append("Keep backlog families for coverage, but do not spend the first expansion budget there.")
    next_actions.append("Preserve the observed planner-sensitive seed lane as a reference slice while harder Layer 4 generation is expanding.")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "target_freeze_ready_count": target_freeze_ready_count,
        "current_freeze_ready_count": freeze_ready_count,
        "freeze_ready_gap": freeze_ready_gap,
        "family_priorities": family_plans,
        "observed_reference_families": _observed_reference_families(candidate_rows),
        "next_actions": next_actions,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# Layer 4 Generation Priority v0.3.2",
        "",
        f"- status: `{payload.get('status')}`",
        f"- current_freeze_ready_count: `{payload.get('current_freeze_ready_count')}`",
        f"- target_freeze_ready_count: `{payload.get('target_freeze_ready_count')}`",
        f"- freeze_ready_gap: `{payload.get('freeze_ready_gap')}`",
        "",
        "## Family Priorities",
        "",
    ]
    for row in payload.get("family_priorities") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"### {row.get('family_label')}")
        lines.append("")
        lines.append(f"- priority_bucket: `{row.get('priority_bucket')}`")
        lines.append(f"- priority_score: `{row.get('priority_score')}`")
        lines.append(f"- recommended_new_task_target: `{row.get('recommended_new_task_target')}`")
        lines.append(f"- current_proxy_count: `{row.get('current_proxy_count')}`")
        lines.append(f"- excluded_easy_count: `{row.get('excluded_easy_count')}`")
        for reason in row.get("rationales") or []:
            lines.append(f"- rationale: {reason}")
        for axis in row.get("generation_axes") or []:
            lines.append(f"- generation_axis: {axis}")
        lines.append("")
    reference_rows = payload.get("observed_reference_families") if isinstance(payload.get("observed_reference_families"), list) else []
    if reference_rows:
        lines.append("## Observed Reference Families")
        lines.append("")
        for row in reference_rows:
            if not isinstance(row, dict):
                continue
            lines.append(f"- `{row.get('family_id')}`: freeze_ready_observed=`{row.get('observed_freeze_ready_count')}`, planner_decisive=`{row.get('planner_decisive_count')}`")
        lines.append("")
    lines.append("## Next Actions")
    lines.append("")
    for index, action in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{index}. {action}")
    lines.append("")
    return "\n".join(lines)


def run_generation_priority(
    *,
    family_spec_path: str = DEFAULT_FAMILY_SPEC,
    hard_lane_summary_path: str = DEFAULT_HARD_LANE_SUMMARY,
    expansion_summary_path: str = DEFAULT_EXPANSION_SUMMARY,
    expansion_taskset_path: str = DEFAULT_EXPANSION_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = build_generation_priority(
        family_spec_path=family_spec_path,
        hard_lane_summary_path=hard_lane_summary_path,
        expansion_summary_path=expansion_summary_path,
        expansion_taskset_path=expansion_taskset_path,
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan harder Layer 4 generation priorities for v0.3.2 Track C expansion.")
    parser.add_argument("--family-spec", default=DEFAULT_FAMILY_SPEC)
    parser.add_argument("--hard-lane-summary", default=DEFAULT_HARD_LANE_SUMMARY)
    parser.add_argument("--expansion-summary", default=DEFAULT_EXPANSION_SUMMARY)
    parser.add_argument("--expansion-taskset", default=DEFAULT_EXPANSION_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = run_generation_priority(
        family_spec_path=str(args.family_spec),
        hard_lane_summary_path=str(args.hard_lane_summary),
        expansion_summary_path=str(args.expansion_summary),
        expansion_taskset_path=str(args.expansion_taskset),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "freeze_ready_gap": int(payload.get("freeze_ready_gap") or 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
