from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MULTI_CANDIDATE_DIR = REPO_ROOT / "artifacts" / "multi_candidate_trajectory_v0_19_51"
DEFAULT_RETRIEVAL_ATTRIBUTION_PATH = REPO_ROOT / "artifacts" / "retrieval_attribution_v0_19_58" / "summary.json"
DEFAULT_CANDIDATE_DISTILL_PATH = REPO_ROOT / "artifacts" / "mutation_candidate_distill_v0_19_61" / "summary.json"
DEFAULT_MODEL_COMPARISON_PATH = REPO_ROOT / "artifacts" / "model_comparison_v0_19_64" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "full_stack_benchmark_v0_19_65"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_mode_results(results_dir: Path, mode: str) -> list[dict[str, Any]]:
    suffix = f"_{mode}.json"
    rows: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob(f"*{suffix}")):
        payload = load_json(path)
        if payload:
            payload["artifact_path"] = str(path)
            rows.append(payload)
    return rows


def summarize_arm(rows: list[dict[str, Any]], *, arm_name: str) -> dict[str, Any]:
    total = len(rows)
    pass_count = sum(1 for row in rows if str(row.get("final_status") or "") == "pass")
    total_rounds = 0
    any_sim_rounds = 0
    pooled_sim_pass = 0
    pooled_candidates = 0
    for row in rows:
        for round_row in row.get("rounds") or []:
            total_rounds += 1
            if round_row.get("any_simulate_pass"):
                any_sim_rounds += 1
            num_candidates = int(round_row.get("num_candidates") or row.get("num_candidates_per_round") or 0)
            pooled_candidates += max(0, num_candidates)
            pooled_sim_pass += int(round_row.get("coverage_simulate_pass") or 0)
    return {
        "arm_name": arm_name,
        "case_count": total,
        "pass_count": pass_count,
        "fail_count": total - pass_count,
        "clean_pass_rate": pass_count / total if total else 0.0,
        "per_round_any_simulate_pass_rate": any_sim_rounds / total_rounds if total_rounds else 0.0,
        "per_round_any_simulate_pass_count": any_sim_rounds,
        "round_count": total_rounds,
        "pooled_simulate_pass_rate": pooled_sim_pass / pooled_candidates if pooled_candidates else 0.0,
        "pooled_simulate_pass_count": pooled_sim_pass,
        "pooled_candidate_count": pooled_candidates,
        "case_results": [
            {
                "candidate_id": row.get("candidate_id"),
                "final_status": row.get("final_status"),
                "round_count": row.get("round_count"),
            }
            for row in rows
        ],
    }


def build_capability_gate_summary(
    *,
    retrieval_attribution: dict[str, Any],
    candidate_distill: dict[str, Any],
    model_comparison: dict[str, Any],
) -> dict[str, Any]:
    disabled = [
        {
            "capability": "static_tool_observation",
            "source_version": "v0.19.54",
            "decision": "disabled",
            "reason": "negative_hot_hard_case_signal",
        },
        {
            "capability": "retrieval_augmented_repair_default",
            "source_version": "v0.19.58",
            "decision": "disabled",
            "reason": "hot_set_regression_despite_cold_uplift",
            "evidence": {
                "mechanism_counts": retrieval_attribution.get("mechanism_counts", {}),
                "transition_counts": retrieval_attribution.get("transition_counts", {}),
            },
        },
        {
            "capability": "structured_generation_prompt",
            "source_version": "v0.19.63",
            "decision": "disabled",
            "reason": "negative_generation_distribution_shift",
        },
        {
            "capability": "multi_model_generalization_claim",
            "source_version": "v0.19.64",
            "decision": "caveat",
            "reason": "model_agnostic_milestone_incomplete",
            "evidence": {
                "status": model_comparison.get("status"),
                "blocked_profiles": model_comparison.get("blocked_profiles", []),
            },
        },
    ]
    isolated_candidates = {
        "source_version": "v0.19.61",
        "decision": "reported_not_scored_in_hard_case_pass_rate",
        "isolation_status": candidate_distill.get("isolation_status"),
        "admitted_count": candidate_distill.get("admitted_count", 0),
        "admitted_count_by_bucket": candidate_distill.get("admitted_count_by_bucket", {}),
    }
    enabled = [
        {
            "capability": "multi_candidate_sampling_omc_residual_ranker",
            "source_version": "v0.19.51",
            "decision": "enabled",
            "reason": "positive_hard_case_clean_pass_delta",
        }
    ]
    return {
        "enabled_capabilities": enabled,
        "disabled_or_caveated_capabilities": disabled,
        "isolated_candidate_pool": isolated_candidates,
    }


def build_full_stack_summary(
    *,
    baseline_rows: list[dict[str, Any]],
    stack_rows: list[dict[str, Any]],
    retrieval_attribution: dict[str, Any],
    candidate_distill: dict[str, Any],
    model_comparison: dict[str, Any],
) -> dict[str, Any]:
    baseline = summarize_arm(baseline_rows, arm_name="baseline")
    stack = summarize_arm(stack_rows, arm_name="evidence_gated_stack")
    delta = stack["clean_pass_rate"] - baseline["clean_pass_rate"]
    gates = build_capability_gate_summary(
        retrieval_attribution=retrieval_attribution,
        candidate_distill=candidate_distill,
        model_comparison=model_comparison,
    )
    status_counts = Counter(
        row.get("final_status")
        for row in stack_rows
    )
    return {
        "version": "v0.19.65",
        "status": "PASS" if stack["clean_pass_rate"] >= 0.5 else "FAIL",
        "benchmark_mode": "evidence_gated_full_stack",
        "baseline_arm": baseline,
        "full_stack_arm": stack,
        "clean_pass_delta_vs_baseline": round(delta, 6),
        "success_criterion": "evidence_gated_stack_clean_pass_rate >= 0.5",
        "success_criterion_met": stack["clean_pass_rate"] >= 0.5,
        "stack_final_status_counts": dict(sorted(status_counts.items())),
        "capability_gates": gates,
        "conclusion": (
            "evidence_gated_stack_breaks_hard_case_50_percent_threshold"
            if stack["clean_pass_rate"] >= 0.5
            else "evidence_gated_stack_does_not_break_hard_case_threshold"
        ),
    }


def run_full_stack_benchmark(
    *,
    multi_candidate_dir: Path = DEFAULT_MULTI_CANDIDATE_DIR,
    retrieval_attribution_path: Path = DEFAULT_RETRIEVAL_ATTRIBUTION_PATH,
    candidate_distill_path: Path = DEFAULT_CANDIDATE_DISTILL_PATH,
    model_comparison_path: Path = DEFAULT_MODEL_COMPARISON_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    baseline_rows = load_mode_results(multi_candidate_dir, "baseline")
    stack_rows = load_mode_results(multi_candidate_dir, "multi-c5")
    summary = build_full_stack_summary(
        baseline_rows=baseline_rows,
        stack_rows=stack_rows,
        retrieval_attribution=load_json(retrieval_attribution_path),
        candidate_distill=load_json(candidate_distill_path),
        model_comparison=load_json(model_comparison_path),
    )
    write_full_stack_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_full_stack_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "REPORT.md").write_text(render_full_stack_report(summary), encoding="utf-8")


def render_full_stack_report(summary: dict[str, Any]) -> str:
    baseline = summary.get("baseline_arm") or {}
    stack = summary.get("full_stack_arm") or {}
    gates = summary.get("capability_gates") or {}
    lines = [
        "# v0.19.65 Evidence-Gated Full Stack Benchmark",
        "",
        f"- status: `{summary.get('status')}`",
        f"- success_criterion_met: `{summary.get('success_criterion_met')}`",
        f"- baseline_clean_pass_rate: `{baseline.get('clean_pass_rate')}`",
        f"- stack_clean_pass_rate: `{stack.get('clean_pass_rate')}`",
        f"- clean_pass_delta_vs_baseline: `{summary.get('clean_pass_delta_vs_baseline')}`",
        "",
        "## Enabled Capabilities",
    ]
    for row in gates.get("enabled_capabilities") or []:
        lines.append(f"- `{row.get('capability')}` from `{row.get('source_version')}`")
    lines.extend(["", "## Disabled Or Caveated Capabilities"])
    for row in gates.get("disabled_or_caveated_capabilities") or []:
        lines.append(f"- `{row.get('capability')}`: `{row.get('decision')}` because `{row.get('reason')}`")
    isolated = gates.get("isolated_candidate_pool") or {}
    lines.extend(
        [
            "",
            "## Isolated Candidate Pool",
            f"- admitted_count: `{isolated.get('admitted_count')}`",
            f"- isolation_status: `{isolated.get('isolation_status')}`",
        ]
    )
    return "\n".join(lines) + "\n"

