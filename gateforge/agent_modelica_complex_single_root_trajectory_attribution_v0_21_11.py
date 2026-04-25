from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_DIRS = [
    REPO_ROOT / "artifacts" / "complex_single_root_repair_trajectory_v0_21_10_strict",
]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "complex_single_root_trajectory_attribution_v0_21_11"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_raw_payloads(run_dir: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    raw_dir = run_dir / "raw"
    rows: list[tuple[str, Path, dict[str, Any]]] = []
    if not raw_dir.exists():
        return rows
    for path in sorted(raw_dir.glob("*.json")):
        payload = load_json(path)
        if payload:
            rows.append((run_dir.name, path, payload))
    return rows


def mutation_family_from_id(candidate_id: str) -> str:
    text = str(candidate_id or "")
    if "_signal_source_migration_partial_" in text:
        return "signal_source_migration_partial"
    if "_measurement_abstraction_partial_" in text:
        return "measurement_abstraction_partial"
    if "_namespace_migration_partial_" in text:
        return "namespace_migration_partial"
    return "unknown"


def observed_error_sequence(payload: dict[str, Any]) -> list[str]:
    return [str(row.get("observed_failure_type") or "") for row in payload.get("attempts") or []]


def text_length_trace(payload: dict[str, Any]) -> list[int]:
    lengths: list[int] = []
    for attempt in payload.get("attempts") or []:
        checkpoint = attempt.get("candidate_text_checkpoint") or {}
        value = checkpoint.get("model_text_len")
        try:
            lengths.append(int(value))
        except (TypeError, ValueError):
            continue
    return lengths


def count_service_unavailable(payload: dict[str, Any]) -> int:
    raw = json.dumps(payload, sort_keys=True)
    return raw.count("service_unavailable")


def count_provider_errors(payload: dict[str, Any]) -> int:
    count = 0
    for attempt in payload.get("attempts") or []:
        repair = attempt.get("declaration_fix_repair") or {}
        if str(repair.get("err") or "").strip():
            count += 1
    return count


def count_applied_repairs(payload: dict[str, Any]) -> int:
    count = 0
    for attempt in payload.get("attempts") or []:
        repair = attempt.get("declaration_fix_repair") or {}
        if bool(repair.get("applied")):
            count += 1
    return count


def max_same_error_streak(sequence: list[str]) -> int:
    best = 0
    current = 0
    previous = None
    for item in sequence:
        if item == previous:
            current += 1
        else:
            current = 1
            previous = item
        best = max(best, current)
    return best


def saw_layer_transition(sequence: list[str]) -> bool:
    return "model_check_error" in sequence and any(
        item in sequence for item in ("constraint_violation", "simulate_error", "none")
    )


def attribute_case(payload: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(payload.get("task_id") or "")
    sequence = observed_error_sequence(payload)
    status = str(payload.get("executor_status") or "").upper()
    pass_status = status == "PASS"
    family = mutation_family_from_id(candidate_id)
    lengths = text_length_trace(payload)
    service_unavailable_count = count_service_unavailable(payload)
    provider_error_count = count_provider_errors(payload)
    applied_repair_count = count_applied_repairs(payload)
    layer_transition = saw_layer_transition(sequence)
    unique_length_count = len(set(lengths))
    same_error_streak = max_same_error_streak(sequence)

    if pass_status and layer_transition and len(sequence) >= 3:
        attribution = "repairable_multiturn_layer_transition"
    elif pass_status:
        attribution = "repairable_direct_or_short_path"
    elif service_unavailable_count:
        attribution = "infra_noise_provider_service_unavailable"
    elif sequence and set(sequence) == {"model_check_error"}:
        if applied_repair_count and unique_length_count <= 2:
            attribution = "model_check_stall_low_observable_variation"
        elif applied_repair_count:
            attribution = "model_check_stall_after_llm_edits"
        else:
            attribution = "model_check_early_stop_without_applied_repair"
    elif layer_transition:
        attribution = "unresolved_after_layer_transition"
    else:
        attribution = "unresolved_without_clear_progress"

    return {
        "candidate_id": candidate_id,
        "mutation_family": family,
        "executor_status": "PASS" if pass_status else "FAILED",
        "n_turns": len(sequence),
        "observed_error_sequence": sequence,
        "saw_layer_transition": layer_transition,
        "applied_repair_count": applied_repair_count,
        "provider_error_count": provider_error_count,
        "service_unavailable_count": service_unavailable_count,
        "text_length_trace": lengths,
        "unique_text_length_count": unique_length_count,
        "max_same_error_streak": same_error_streak,
        "failure_attribution": attribution,
        "strict_no_auxiliary_packs": not any(
            [
                bool(payload.get("remedy_pack_enabled")),
                bool(payload.get("capability_intervention_pack_enabled")),
                bool(payload.get("broader_change_pack_enabled")),
                bool((payload.get("experience_replay") or {}).get("used")),
                bool((payload.get("planner_experience_injection") or {}).get("used")),
            ]
        ),
    }


def summarize_by_family(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        grouped[str(row.get("mutation_family") or "unknown")].append(row)

    summary: dict[str, Any] = {}
    for family, rows in sorted(grouped.items()):
        pass_rows = [row for row in rows if row.get("executor_status") == "PASS"]
        multiturn_rows = [
            row for row in pass_rows if int(row.get("n_turns") or 0) >= 3 and row.get("saw_layer_transition")
        ]
        attributions = Counter(str(row.get("failure_attribution") or "") for row in rows)
        low_variation_failures = sum(
            1 for row in rows if row.get("failure_attribution") == "model_check_stall_low_observable_variation"
        )
        model_check_stalls = sum(
            1 for row in rows if str(row.get("failure_attribution") or "").startswith("model_check_stall")
        )
        summary[family] = {
            "case_count": len(rows),
            "pass_count": len(pass_rows),
            "pass_rate": len(pass_rows) / len(rows) if rows else 0.0,
            "multiturn_pass_count": len(multiturn_rows),
            "model_check_stall_count": model_check_stalls,
            "low_observable_variation_failure_count": low_variation_failures,
            "attribution_counts": dict(sorted(attributions.items())),
        }
    return summary


def summarize_stability(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in case_rows:
        grouped[str(row.get("candidate_id") or "")].append(row)

    repeated = {candidate_id: rows for candidate_id, rows in grouped.items() if len(rows) > 1}
    stable_pass = 0
    stable_fail = 0
    unstable = 0
    for rows in repeated.values():
        statuses = {str(row.get("executor_status") or "") for row in rows}
        if statuses == {"PASS"}:
            stable_pass += 1
        elif statuses == {"FAILED"}:
            stable_fail += 1
        elif len(statuses) > 1:
            unstable += 1
    return {
        "run_count_per_case": {candidate_id: len(rows) for candidate_id, rows in sorted(grouped.items())},
        "repeated_case_count": len(repeated),
        "stable_pass_case_count": stable_pass,
        "stable_fail_case_count": stable_fail,
        "unstable_status_case_count": unstable,
        "stability_status": "single_run_only" if not repeated else "repeat_evidence_available",
    }


def build_trajectory_attribution(
    *,
    run_dirs: list[Path] = DEFAULT_RUN_DIRS,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    case_rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        for run_id, raw_path, payload in load_raw_payloads(run_dir):
            row = attribute_case(payload)
            row["run_id"] = run_id
            row["raw_artifact_path"] = str(raw_path)
            case_rows.append(row)

    pass_count = sum(1 for row in case_rows if row.get("executor_status") == "PASS")
    multiturn_pass_count = sum(
        1
        for row in case_rows
        if row.get("executor_status") == "PASS"
        and int(row.get("n_turns") or 0) >= 3
        and row.get("saw_layer_transition")
    )
    family_summary = summarize_by_family(case_rows)
    stability = summarize_stability(case_rows)
    strict = all(bool(row.get("strict_no_auxiliary_packs")) for row in case_rows)

    conclusion = "trajectory_attribution_ready"
    if stability.get("stability_status") == "single_run_only":
        next_action = "repeat_strict_runs_before_promoting_stability_claim"
    else:
        next_action = "decide_between_diversity_live_ab_and_family_expansion"

    summary = {
        "version": "v0.21.11",
        "status": "PASS" if case_rows else "REVIEW",
        "case_observation_count": len(case_rows),
        "run_dir_count": len(run_dirs),
        "pass_count": pass_count,
        "pass_rate": pass_count / len(case_rows) if case_rows else 0.0,
        "multiturn_pass_count": multiturn_pass_count,
        "multiturn_pass_rate": multiturn_pass_count / len(case_rows) if case_rows else 0.0,
        "strict_no_auxiliary_packs": strict,
        "family_summary": family_summary,
        "stability": stability,
        "conclusion": conclusion,
        "next_action": next_action,
        "discipline": "attribution_only_no_repair_logic_no_routing_no_hint",
    }
    write_outputs(out_dir=out_dir, rows=case_rows, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "case_attribution.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
