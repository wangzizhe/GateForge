from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_planner_sensitive_expansion_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_planner_sensitive_expansion_v0_3_2"
DEFAULT_TARGET_CANDIDATE_COUNT = 24
DEFAULT_TARGET_FREEZE_READY_COUNT = 20
DEFAULT_SOURCE_GROUPS = (
    {
        "group_id": "observed_planner_sensitive_seed",
        "group_label": "Observed Planner-Sensitive Seed",
        "source_taskset_path": "artifacts/agent_modelica_planner_sensitive_taskset_builder_v1/taskset_frozen.json",
        "results_paths": [
            "artifacts/agent_modelica_planner_sensitive_attribution_repair_v0_3_2/experience_baseline.json",
        ],
        "evidence_tier": "observed_planner_sensitive",
    },
    {
        "group_id": "layer4_hard_lane_proxy",
        "group_label": "Layer 4 Hard-Lane Proxy",
        "source_taskset_path": "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/taskset_frozen.json",
        "results_paths": [
            "artifacts/agent_modelica_l4_realism_evidence_v1/main_l5/l4/off/run_results.json",
            "artifacts/agent_modelica_wave2_1_harder_dynamics_evidence_v1/deterministic_on/results.json",
            "artifacts/agent_modelica_multi_round_failure_live_evidence_v1/runs/multi_round_live_baseline_04/baseline_off_live/results.json",
        ],
        "evidence_tier": "layer4_proxy",
    },
    {
        "group_id": "harder_holdout_exclusion_check",
        "group_label": "Harder Holdout Exclusion Check",
        "source_taskset_path": "artifacts/agent_modelica_layer4_holdout_v0_3_1/taskset_frozen.json",
        "results_paths": [
            "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/baseline/gf_results.json",
        ],
        "evidence_tier": "deterministic_exclusion_reference",
    },
)


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


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else payload.get("cases")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _result_rows(payload: dict) -> list[dict]:
    rows = payload.get("records") if isinstance(payload.get("records"), list) else payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id"))


def _success(row: dict) -> bool:
    if bool(row.get("passed")) or bool(row.get("success")):
        return True
    hard_checks = row.get("hard_checks") if isinstance(row.get("hard_checks"), dict) else {}
    return bool(
        hard_checks.get("check_model_pass")
        and hard_checks.get("simulate_pass")
        and hard_checks.get("physics_contract_pass", True)
        and hard_checks.get("regression_pass", True)
    )


def _results_index(results_paths: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in results_paths:
        payload = _load_json(path)
        for row in _result_rows(payload):
            item_id = _item_id(row)
            if not item_id or item_id in out:
                continue
            out[item_id] = dict(row)
    return out


def _observed_seed_score(task: dict, result: dict) -> tuple[int, list[str], str]:
    score = 0
    reasons: list[str] = []
    resolution_path = _norm(result.get("resolution_path"))
    if resolution_path in {"llm_planner_assisted", "rule_then_llm"}:
        reasons.append(f"observed_resolution_path:{resolution_path}")
        score += 6
    if bool(result.get("planner_invoked")):
        reasons.append("planner_invoked_observed")
        score += 4
    if bool(result.get("planner_decisive")):
        reasons.append("planner_decisive_observed")
        score += 2
    if int(task.get("expected_rounds_min") or 0) >= 2:
        reasons.append("expected_multi_round")
        score += 1
    return score, reasons, "freeze_ready_observed"


def _proxy_score(task: dict, result: dict | None) -> tuple[int, list[str], str]:
    score = 0
    reasons: list[str] = []
    expected_layer_hint = _norm(task.get("expected_layer_hint"))
    if expected_layer_hint == "layer_4":
        reasons.append("expected_layer_hint_layer_4")
        score += 3
    if int(task.get("expected_rounds_min") or 0) >= 2:
        reasons.append("expected_multi_round")
        score += 2
    if bool(task.get("simulate_phase_required")):
        reasons.append("simulate_phase_required")
        score += 1
    if int(task.get("mock_success_round") or 0) >= 2:
        reasons.append("mock_success_round_ge_2")
        score += 1
    if int(task.get("cascade_depth") or 0) >= 2:
        reasons.append("cascade_depth_ge_2")
        score += 1
    if result is None:
        reasons.append("no_direct_outcome_available")
        return score, reasons, "proxy_candidate"

    passed = _success(result)
    rounds_used = int(result.get("rounds_used") or 0)
    if not passed:
        reasons.append("source_result_not_yet_solved")
        score += 3
        return score, reasons, "proxy_candidate"
    if rounds_used >= 2:
        reasons.append("source_result_multi_round")
        score += 2
        return score, reasons, "proxy_candidate"
    reasons.append("source_result_single_round_success")
    return -1, reasons, "exclude_easy_proxy"


def build_expansion_candidates(
    *,
    source_groups: list[dict] | None = None,
    target_candidate_count: int = DEFAULT_TARGET_CANDIDATE_COUNT,
    target_freeze_ready_count: int = DEFAULT_TARGET_FREEZE_READY_COUNT,
) -> dict:
    groups = [dict(row) for row in (source_groups or list(DEFAULT_SOURCE_GROUPS))]
    candidates: list[dict] = []
    excluded: list[dict] = []
    missing_sources: list[str] = []
    seen: set[str] = set()

    harder_holdout_easy: set[str] = set()
    for group in groups:
        if _norm(group.get("evidence_tier")) != "deterministic_exclusion_reference":
            continue
        results_index = _results_index([str(path) for path in (group.get("results_paths") or []) if _norm(path)])
        for item_id, result in results_index.items():
            if _success(result) and _norm(result.get("resolution_path")) == "deterministic_rule_only":
                harder_holdout_easy.add(item_id)

    for group in groups:
        evidence_tier = _norm(group.get("evidence_tier"))
        if evidence_tier == "deterministic_exclusion_reference":
            continue
        source_path = _norm(group.get("source_taskset_path"))
        payload = _load_json(source_path)
        if not payload:
            missing_sources.append(source_path)
            continue
        tasks = _task_rows(payload)
        results_index = _results_index([str(path) for path in (group.get("results_paths") or []) if _norm(path)])

        for task in tasks:
            item_id = _item_id(task)
            if not item_id or item_id in seen:
                continue
            result = results_index.get(item_id)
            if evidence_tier == "observed_planner_sensitive":
                score, reasons, classification = _observed_seed_score(task, result or {})
            else:
                score, reasons, classification = _proxy_score(task, result)
            if item_id in harder_holdout_easy:
                reasons.append("excluded_due_to_harder_holdout_deterministic_success")
                classification = "exclude_easy_proxy"
                score = -1
            row = {
                "item_id": item_id,
                "group_id": _norm(group.get("group_id")),
                "group_label": _norm(group.get("group_label") or group.get("group_id")),
                "evidence_tier": evidence_tier,
                "classification": classification,
                "selection_score": int(score),
                "selection_reasons": reasons,
                "expected_layer_hint": _norm(task.get("expected_layer_hint")),
                "expected_rounds_min": int(task.get("expected_rounds_min") or 0),
                "failure_type": _norm(task.get("failure_type") or task.get("expected_failure_type")),
                "source_taskset_path": source_path,
            }
            if score < 0 or classification.startswith("exclude"):
                excluded.append(row)
                continue
            seen.add(item_id)
            candidates.append({**dict(task), **row})

    candidates.sort(
        key=lambda row: (
            0 if _norm(row.get("classification")) == "freeze_ready_observed" else 1,
            -int(row.get("selection_score") or 0),
            -int(row.get("expected_rounds_min") or 0),
            _norm(row.get("item_id")),
        )
    )
    if int(target_candidate_count or 0) > 0:
        candidates = candidates[: int(target_candidate_count)]

    freeze_ready_count = len([row for row in candidates if _norm(row.get("classification")) == "freeze_ready_observed"])
    proxy_count = len([row for row in candidates if _norm(row.get("classification")) == "proxy_candidate"])
    status = "PASS"
    if freeze_ready_count < int(target_freeze_ready_count or 0):
        status = "NEEDS_MORE_GENERATION"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "target_candidate_count": int(target_candidate_count),
        "target_freeze_ready_count": int(target_freeze_ready_count),
        "selected_candidate_count": len(candidates),
        "freeze_ready_count": freeze_ready_count,
        "proxy_candidate_count": proxy_count,
        "needs_new_mutation_generation_for_freeze_ready_slice": freeze_ready_count < int(target_freeze_ready_count or 0),
        "source_groups": groups,
        "missing_sources": missing_sources,
        "excluded_rows": excluded,
        "selected_rows": candidates,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# Planner-Sensitive Expansion v0.3.2",
        "",
        f"- status: `{_norm(payload.get('status'))}`",
        f"- selected_candidate_count: `{payload.get('selected_candidate_count')}`",
        f"- freeze_ready_count: `{payload.get('freeze_ready_count')}`",
        f"- proxy_candidate_count: `{payload.get('proxy_candidate_count')}`",
        f"- needs_new_mutation_generation_for_freeze_ready_slice: `{payload.get('needs_new_mutation_generation_for_freeze_ready_slice')}`",
        "",
        "## Interpretation",
        "",
    ]
    if bool(payload.get("needs_new_mutation_generation_for_freeze_ready_slice")):
        lines.append("- current observed planner-sensitive seed coverage is still below the freeze-ready target")
        lines.append("- current Layer 4 proxy candidates can expand the candidate pool, but they are not equivalent to validated planner-sensitive observations")
        lines.append("- new harder Layer 4 / Layer 4+ mutation generation is still required before a paper-grade comparative slice can be frozen")
    else:
        lines.append("- current observed and proxy evidence is sufficient to freeze a larger planner-sensitive comparative slice")
    lines.append("")
    lines.append("## Selected Candidates")
    lines.append("")
    for row in payload.get("selected_rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"### {_norm(row.get('item_id'))}")
        lines.append("")
        lines.append(f"- classification: `{_norm(row.get('classification'))}`")
        lines.append(f"- evidence_tier: `{_norm(row.get('evidence_tier'))}`")
        lines.append(f"- group_id: `{_norm(row.get('group_id'))}`")
        lines.append(f"- failure_type: `{_norm(row.get('failure_type'))}`")
        lines.append(f"- expected_layer_hint: `{_norm(row.get('expected_layer_hint'))}`")
        lines.append(f"- expected_rounds_min: `{int(row.get('expected_rounds_min') or 0)}`")
        lines.append(f"- selection_reasons: `{'; '.join(str(item) for item in (row.get('selection_reasons') or []))}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_expansion(
    *,
    out_dir: str = DEFAULT_OUT_DIR,
    source_groups: list[dict] | None = None,
    target_candidate_count: int = DEFAULT_TARGET_CANDIDATE_COUNT,
    target_freeze_ready_count: int = DEFAULT_TARGET_FREEZE_READY_COUNT,
) -> dict:
    payload = build_expansion_candidates(
        source_groups=source_groups,
        target_candidate_count=target_candidate_count,
        target_freeze_ready_count=target_freeze_ready_count,
    )
    out_root = Path(out_dir)
    taskset_payload = {
        "schema_version": "agent_modelica_taskset_frozen_v1",
        "generated_at_utc": _now_utc(),
        "lane_id": "planner_sensitive_expansion_v0_3_2",
        "label": "Planner-Sensitive Expansion Candidates v0.3.2",
        "task_count": int(payload.get("selected_candidate_count") or 0),
        "planner_sensitive_expansion_metadata": {
            "schema_version": SCHEMA_VERSION,
            "status": _norm(payload.get("status")),
            "freeze_ready_count": int(payload.get("freeze_ready_count") or 0),
            "proxy_candidate_count": int(payload.get("proxy_candidate_count") or 0),
            "needs_new_mutation_generation_for_freeze_ready_slice": bool(
                payload.get("needs_new_mutation_generation_for_freeze_ready_slice")
            ),
        },
        "tasks": [dict(row) for row in (payload.get("selected_rows") or []) if isinstance(row, dict)],
    }
    _write_json(out_root / "taskset_candidates.json", taskset_payload)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a planner-sensitive expansion candidate slice from observed seeds and Layer 4 proxies.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--target-candidate-count", type=int, default=DEFAULT_TARGET_CANDIDATE_COUNT)
    parser.add_argument("--target-freeze-ready-count", type=int, default=DEFAULT_TARGET_FREEZE_READY_COUNT)
    args = parser.parse_args()
    payload = run_expansion(
        out_dir=str(args.out_dir),
        target_candidate_count=int(args.target_candidate_count),
        target_freeze_ready_count=int(args.target_freeze_ready_count),
    )
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "selected_candidate_count": int(payload.get("selected_candidate_count") or 0),
                "freeze_ready_count": int(payload.get("freeze_ready_count") or 0),
            }
        )
    )


if __name__ == "__main__":
    main()
