"""
Decision attribution for the Modelica repair agent.

Reads the completed executor run result (with attempts[] list) and identifies
the causal path that led to success or failure:

  direct           -- plan_0 was correct, resolved in round 1
  replan_corrected -- a replan changed direction and led to resolution
  guided_search    -- guided search budget in the decisive round was key
  exhaustive       -- resolved without LLM guidance, just iterated actions
  failed           -- never resolved within the allowed rounds

Transferable skill: causal tracing in AI agent systems -- identifying which
specific decision node in the agent's reasoning chain affected the outcome.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_decision_attribution_v1"

# Named repair method keys written into each attempt record by the executor.
_REPAIR_METHOD_KEYS = (
    "pre_repair",
    "initialization_marker_repair",
    "wave2_marker_repair",
    "wave2_1_marker_repair",
    "wave2_2_marker_repair",
    "multi_round_layered_repair",
    "source_blind_multistep_local_search",
    "source_blind_multistep_exposure_repair",
    "source_blind_local_repair",
    "source_repair",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decisive_round(attempts: list[dict]) -> int | None:
    """Return the round number of the first attempt that passed check + simulate."""
    for attempt in attempts:
        if attempt.get("check_model_pass") and attempt.get("simulate_pass"):
            return int(attempt.get("round") or 0) or None
    return None


def _first_plan_verdict(attempts: list[dict]) -> str:
    """
    Determine whether the first LLM plan's branch selection was correct.

    Returns "correct", "wrong", or "unknown" (field absent or no LLM plan used).
    """
    if not attempts:
        return "unknown"
    first = attempts[0]
    val = first.get("first_plan_branch_match")
    if val is True:
        return "correct"
    if val is False:
        return "wrong"
    return "unknown"


def _replan_corrected(attempts: list[dict]) -> bool:
    """True if any round used a replan that resolved the issue."""
    for attempt in attempts:
        if attempt.get("replan_used") and attempt.get("replan_resolved"):
            return True
    return False


def _decisive_attempt(attempts: list[dict], decisive_rnd: int) -> dict | None:
    for attempt in attempts:
        if int(attempt.get("round") or 0) == decisive_rnd:
            return attempt
    return None


def _extract_decisive_actions(attempt: dict) -> list[str]:
    """Collect names of repair methods that were applied in this attempt."""
    applied = []
    for key in _REPAIR_METHOD_KEYS:
        val = attempt.get(key)
        if isinstance(val, dict) and val.get("applied"):
            applied.append(key)
    # Also collect from l4.applied_actions if present
    l4 = attempt.get("l4") if isinstance(attempt.get("l4"), dict) else {}
    for action in l4.get("applied_actions") or []:
        if isinstance(action, dict):
            op = str(action.get("op") or "").strip()
            tag = str(action.get("reason_tag") or "").strip()
            src = str(action.get("source") or "").strip()
            parts = [x for x in [op, tag, src] if x]
            key = "|".join(parts) if parts else "unknown"
            if key not in applied:
                applied.append(key)
    return applied


def _wasted_rounds(attempts: list[dict]) -> int:
    """Count rounds where the observed failure type did not change from the previous round."""
    wasted = 0
    prev_type = None
    for attempt in attempts:
        cur_type = str(attempt.get("observed_failure_type") or "")
        if prev_type is not None and cur_type == prev_type and cur_type:
            wasted += 1
        prev_type = cur_type
    return wasted


def _diagnostic_progression(attempts: list[dict]) -> list[list]:
    """Return [(round, observed_failure_type)] showing how the error type evolved."""
    progression = []
    for attempt in attempts:
        rnd = int(attempt.get("round") or 0)
        ft = str(attempt.get("observed_failure_type") or "")
        progression.append([rnd, ft])
    return progression


def _causal_path(
    *,
    decisive_rnd: int | None,
    first_verdict: str,
    replan_ok: bool,
    decisive_attempt_rec: dict | None,
) -> tuple[str, str]:
    """Return (causal_path, causal_path_reason)."""
    if decisive_rnd is None:
        return "failed", "no round passed check_model and simulate within budget"
    if decisive_rnd == 1 and first_verdict == "correct":
        return "direct", "plan_0 branch was correct and resolved in round 1"
    if replan_ok:
        return "replan_corrected", "a replan changed direction and the task resolved"
    if decisive_attempt_rec is not None:
        if decisive_attempt_rec.get("guided_search_used") and decisive_attempt_rec.get(
            "guided_search_resolution"
        ):
            return "guided_search", "guided search budget drove the decisive round"
    return "exhaustive", "resolved through action iteration without LLM plan correction"


def attribute_decision(run_result: dict) -> dict:
    """
    Produce a DecisionAttributionRecord from a single executor run result.

    Args:
        run_result: the JSON payload produced by the executor for one task.
                    Must contain an "attempts" list.

    Returns:
        dict conforming to SCHEMA_VERSION.
    """
    attempts = run_result.get("attempts") or []
    task_id = str(run_result.get("task_id") or "")
    failure_type = str(run_result.get("failure_type") or "")

    decisive_rnd = _decisive_round(attempts)
    first_verdict = _first_plan_verdict(attempts)
    replan_ok = _replan_corrected(attempts)
    dec_attempt = _decisive_attempt(attempts, decisive_rnd) if decisive_rnd is not None else None
    path, path_reason = _causal_path(
        decisive_rnd=decisive_rnd,
        first_verdict=first_verdict,
        replan_ok=replan_ok,
        decisive_attempt_rec=dec_attempt,
    )
    decisive_actions = _extract_decisive_actions(dec_attempt) if dec_attempt is not None else []
    llm_decisive = bool(dec_attempt.get("llm_plan_was_decisive")) if dec_attempt is not None else False
    wasted = _wasted_rounds(attempts)
    progression = _diagnostic_progression(attempts)
    physics_in_decisive: bool | None = None
    if dec_attempt is not None:
        val = dec_attempt.get("physics_contract_pass")
        physics_in_decisive = bool(val) if val is not None else None
    action_contributions = run_result.get("action_contributions") if isinstance(run_result.get("action_contributions"), list) else []
    action_contributions = [row for row in action_contributions if isinstance(row, dict)]

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "failure_type": failure_type,
        "total_rounds": len(attempts),
        "decisive_round": decisive_rnd,
        "first_plan_verdict": first_verdict,
        "replan_corrected": replan_ok,
        "causal_path": path,
        "causal_path_reason": path_reason,
        "decisive_actions": decisive_actions,
        "llm_was_decisive": llm_decisive,
        "wasted_rounds": wasted,
        "diagnostic_progression": progression,
        "physics_contract_in_decisive": physics_in_decisive,
        "repair_quality_score": float(run_result.get("repair_quality_score") or 0.0),
        "action_contribution_count": len(action_contributions),
        "action_contribution_distribution": {
            "advancing": len([row for row in action_contributions if str(row.get("contribution") or "") == "advancing"]),
            "neutral": len([row for row in action_contributions if str(row.get("contribution") or "") == "neutral"]),
            "regressing": len([row for row in action_contributions if str(row.get("contribution") or "") == "regressing"]),
        },
    }


def summarize_decision_attribution(records: list[dict]) -> dict:
    """
    Aggregate attribution records across multiple tasks.

    Args:
        records: list of dicts produced by attribute_decision().

    Returns:
        summary dict with distribution statistics.
    """
    path_counts: dict[str, int] = {
        "direct": 0,
        "replan_corrected": 0,
        "guided_search": 0,
        "exhaustive": 0,
        "failed": 0,
    }
    first_correct = 0
    replan_corrected_count = 0
    llm_decisive_count = 0
    rounds_to_success: list[float] = []
    wasted_list: list[float] = []
    successful = 0
    path_by_ft: dict[str, dict[str, int]] = {}
    quality_scores: list[float] = []
    quality_distribution = {"high": 0, "medium": 0, "low": 0, "zero": 0}
    action_contribution_distribution = {"advancing": 0, "neutral": 0, "regressing": 0}

    for rec in records:
        path = str(rec.get("causal_path") or "failed")
        path_counts[path] = path_counts.get(path, 0) + 1

        ft = str(rec.get("failure_type") or "unknown")
        ft_dist = path_by_ft.setdefault(ft, {})
        ft_dist[path] = ft_dist.get(path, 0) + 1

        if rec.get("first_plan_verdict") == "correct":
            first_correct += 1

        wasted_list.append(float(rec.get("wasted_rounds") or 0))
        quality = float(rec.get("repair_quality_score") or 0.0)
        quality_scores.append(quality)
        if quality >= 0.8:
            quality_distribution["high"] += 1
        elif quality >= 0.5:
            quality_distribution["medium"] += 1
        elif quality > 0.0:
            quality_distribution["low"] += 1
        else:
            quality_distribution["zero"] += 1
        contrib = rec.get("action_contribution_distribution") if isinstance(rec.get("action_contribution_distribution"), dict) else {}
        for key in action_contribution_distribution:
            action_contribution_distribution[key] += int(contrib.get(key) or 0)

        decisive = rec.get("decisive_round")
        if decisive is not None:
            successful += 1
            rounds_to_success.append(float(decisive))
            if rec.get("replan_corrected"):
                replan_corrected_count += 1
            if rec.get("llm_was_decisive"):
                llm_decisive_count += 1

    total = len(records)
    first_plan_correct_pct = round(first_correct / total * 100, 1) if total else 0.0
    replan_pct = round(replan_corrected_count / successful * 100, 1) if successful else 0.0
    llm_pct = round(llm_decisive_count / successful * 100, 1) if successful else 0.0
    median_rounds = round(statistics.median(rounds_to_success), 1) if rounds_to_success else 0.0
    median_wasted = round(statistics.median(wasted_list), 1) if wasted_list else 0.0

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "total_tasks": total,
        "causal_path_distribution": path_counts,
        "first_plan_correct_pct": first_plan_correct_pct,
        "replan_corrected_pct": replan_pct,
        "llm_decisive_pct": llm_pct,
        "median_rounds_to_success": median_rounds,
        "median_wasted_rounds": median_wasted,
        "median_quality_score": round(statistics.median(quality_scores), 4) if quality_scores else 0.0,
        "quality_distribution": quality_distribution,
        "action_contribution_distribution": action_contribution_distribution,
        "causal_path_by_failure_type": path_by_ft,
    }


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attribute decisions from an executor run-results file."
    )
    parser.add_argument("--run-results", required=True, help="Path to run_results JSON file")
    parser.add_argument("--out", required=True, help="Output path for attribution JSON")
    args = parser.parse_args()

    run_results = _load_json(args.run_results)
    records_raw = run_results.get("records") or []
    if not records_raw:
        # Single-task result (not a batch)
        records_raw = [run_results]

    attribution_records = [attribute_decision(r) for r in records_raw]
    summary = summarize_decision_attribution(attribution_records)

    output = {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "records": attribution_records,
    }
    _write_json(args.out, output)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
