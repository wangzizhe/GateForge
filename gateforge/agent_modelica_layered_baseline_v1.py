from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .physics_contract_v0 import DEFAULT_PHYSICS_CONTRACT_PATH

DEFAULT_FAILURE_TYPES = ("model_check_error", "simulate_error", "semantic_regression")
DEFAULT_SCALES = ("small", "medium", "large")


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    layered = payload.get("layered_pass_rate_pct_by_scale", {})
    lines = [
        "# GateForge Agent Modelica Layered Baseline v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- taskset_status: `{payload.get('taskset_status')}`",
        f"- run_contract_status: `{payload.get('run_contract_status')}`",
        f"- acceptance_status: `{payload.get('acceptance_status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- success_at_k_pct: `{payload.get('success_at_k_pct')}`",
        f"- median_time_to_pass_sec: `{payload.get('median_time_to_pass_sec')}`",
        f"- median_repair_rounds: `{payload.get('median_repair_rounds')}`",
        f"- regression_count: `{payload.get('regression_count')}`",
        f"- physics_fail_count: `{payload.get('physics_fail_count')}`",
        "",
        "## Layered Pass Rate",
        "",
    ]
    if isinstance(layered, dict) and layered:
        for scale in sorted(layered.keys()):
            lines.append(f"- {scale}: `{layered.get(scale)}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Coverage Gaps", ""])
    missing_scales = payload.get("missing_scales", [])
    missing_failure_types = payload.get("missing_failure_types", [])
    if isinstance(missing_scales, list) and missing_scales:
        lines.append(f"- missing_scales: `{','.join(missing_scales)}`")
    else:
        lines.append("- missing_scales: `none`")
    if isinstance(missing_failure_types, list) and missing_failure_types:
        lines.append(f"- missing_failure_types: `{','.join(missing_failure_types)}`")
    else:
        lines.append("- missing_failure_types: `none`")

    missing = payload.get("missing_scale_failure_buckets", [])
    if isinstance(missing, list) and missing:
        lines.extend([f"- `{x}`" for x in missing])
    else:
        lines.append("- `none`")

    lines.extend(["", "## Top Fail Reasons", ""])
    top_fail = payload.get("top_fail_reasons", {})
    if isinstance(top_fail, dict) and top_fail:
        for key, count in sorted(top_fail.items(), key=lambda kv: (-int(kv[1]), kv[0]))[:8]:
            lines.append(f"- {key}: `{count}`")
    else:
        lines.append("- `none`")

    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _run_module(module_name: str, argv: list[str]) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", module_name, *argv],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "module": module_name,
        "argv": argv,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _collect_scale_failure_counts(tasks: list[dict], scales: list[str], failure_types: list[str]) -> tuple[dict, list[str]]:
    matrix = {scale: {ftype: 0 for ftype in failure_types} for scale in scales}
    for row in tasks:
        scale = str(row.get("scale") or "").lower()
        ftype = str(row.get("failure_type") or "").lower()
        if scale in matrix and ftype in matrix[scale]:
            matrix[scale][ftype] = int(matrix[scale][ftype]) + 1

    missing: list[str] = []
    for scale in scales:
        for ftype in failure_types:
            if int(matrix[scale][ftype]) <= 0:
                missing.append(f"{scale}:{ftype}")
    return matrix, missing


def _count_scales_and_failures(tasks: list[dict], scales: list[str], failure_types: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    by_scale = {x: 0 for x in scales}
    by_failure = {x: 0 for x in failure_types}
    for row in tasks:
        scale = str(row.get("scale") or "").lower()
        ftype = str(row.get("failure_type") or "").lower()
        if scale in by_scale:
            by_scale[scale] = int(by_scale[scale]) + 1
        if ftype in by_failure:
            by_failure[ftype] = int(by_failure[ftype]) + 1
    return by_scale, by_failure


def _layered_pass_rates(counts_by_scale: dict, scales: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for scale in scales:
        bucket = counts_by_scale.get(scale) if isinstance(counts_by_scale, dict) else {}
        if not isinstance(bucket, dict):
            bucket = {}
        passed = int(bucket.get("PASS", 0) or 0)
        total = int(bucket.get("PASS", 0) or 0) + int(bucket.get("NEEDS_REVIEW", 0) or 0) + int(bucket.get("FAIL", 0) or 0)
        out[scale] = _ratio(passed, total)
    return out


def _extract_fail_reasons(run_results: list[dict]) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    global_counts: dict[str, int] = {}
    by_scale: dict[str, dict[str, int]] = {}
    for rec in run_results:
        if not isinstance(rec, dict):
            continue
        scale = str(rec.get("scale") or "unknown").lower()
        reasons: list[str] = []
        hard = rec.get("hard_checks") if isinstance(rec.get("hard_checks"), dict) else {}
        if not bool(hard.get("check_model_pass")):
            reasons.append("check_model_fail")
        if not bool(hard.get("simulate_pass")):
            reasons.append("simulate_fail")
        if not bool(hard.get("regression_pass")):
            reasons.append("regression_fail")
        reasons.extend([str(x) for x in (rec.get("physics_contract_reasons") or []) if isinstance(x, str)])
        reasons.extend([str(x) for x in (rec.get("regression_reasons") or []) if isinstance(x, str)])
        dedup = sorted(set(reasons))
        for reason in dedup:
            global_counts[reason] = int(global_counts.get(reason, 0)) + 1
            bucket = by_scale.setdefault(scale, {})
            bucket[reason] = int(bucket.get(reason, 0)) + 1
    return global_counts, by_scale


def _top_n(counter: dict[str, int], n: int = 3) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda kv: (-int(kv[1]), kv[0]))[:n])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run first layered baseline for modelica agent chain")
    parser.add_argument("--mutation-manifest", default="")
    parser.add_argument("--extra-mutation-manifest", action="append", default=[])
    parser.add_argument("--taskset-in", default=None)
    parser.add_argument("--out-dir", default="artifacts/agent_modelica_layered_baseline_v1")
    parser.add_argument("--scales", default=",".join(DEFAULT_SCALES))
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--max-per-scale", type=int, default=9)
    parser.add_argument("--max-per-scale-failure-type", type=int, default=3)
    parser.add_argument("--max-rounds", type=int, default=9)
    parser.add_argument("--max-time-sec", type=int, default=1200)
    parser.add_argument("--small-max-time-sec", type=int, default=180)
    parser.add_argument("--medium-max-time-sec", type=int, default=420)
    parser.add_argument("--large-max-time-sec", type=int, default=900)
    parser.add_argument("--small-max-rounds", type=int, default=3)
    parser.add_argument("--medium-max-rounds", type=int, default=6)
    parser.add_argument("--large-max-rounds", type=int, default=9)
    parser.add_argument("--physics-contract", default=DEFAULT_PHYSICS_CONTRACT_PATH)
    parser.add_argument("--repair-playbook", default=None)
    parser.add_argument("--repair-history", default=None)
    parser.add_argument("--focus-queue", default=None)
    parser.add_argument("--patch-template-adaptations", default=None)
    parser.add_argument("--retrieval-policy", default=None)
    parser.add_argument("--inject-hard-fail-count", type=int, default=0)
    parser.add_argument("--inject-slow-pass-count", type=int, default=0)
    parser.add_argument("--run-mode", choices=["mock", "evidence", "live"], default="mock")
    parser.add_argument("--runtime-threshold", type=float, default=0.2)
    parser.add_argument("--live-executor-cmd", default=None)
    parser.add_argument("--live-timeout-sec", type=int, default=180)
    parser.add_argument("--live-max-output-chars", type=int, default=1200)
    parser.add_argument("--out", default="artifacts/agent_modelica_layered_baseline_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scales = [x.strip().lower() for x in str(args.scales).split(",") if x.strip()]
    if not scales:
        scales = list(DEFAULT_SCALES)
    failure_types = [x.strip().lower() for x in str(args.failure_types).split(",") if x.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    taskset_path = str(out_dir / "taskset.json")
    taskset_summary_path = str(out_dir / "taskset_summary.json")
    injected_taskset_path = str(out_dir / "taskset_injected.json")
    inject_summary_path = str(out_dir / "inject_summary.json")
    run_results_path = str(out_dir / "run_results.json")
    run_summary_path = str(out_dir / "run_summary.json")
    acceptance_path = str(out_dir / "acceptance_summary.json")

    taskset_cmd: dict
    if isinstance(args.taskset_in, str) and args.taskset_in.strip():
        source_taskset = Path(args.taskset_in.strip())
        if not source_taskset.exists():
            raise SystemExit(f"--taskset-in not found: {source_taskset}")
        payload = _load_json(str(source_taskset))
        _write_json(taskset_path, payload)
        copied_summary = {
            "status": "PASS",
            "taskset_out": taskset_path,
            "sources": {"taskset_in": str(source_taskset)},
        }
        _write_json(taskset_summary_path, copied_summary)
        taskset_cmd = {"returncode": 0, "stderr": "", "stdout": "", "module": "taskset_in", "argv": []}
    else:
        if not str(args.mutation_manifest).strip():
            raise SystemExit("--mutation-manifest is required when --taskset-in is not provided")
        taskset_argv = [
            "--mutation-manifest",
            args.mutation_manifest,
            "--scales",
            ",".join(scales),
            "--failure-types",
            ",".join(failure_types),
            "--max-per-scale",
            str(max(1, int(args.max_per_scale))),
            "--max-per-scale-failure-type",
            str(max(0, int(args.max_per_scale_failure_type))),
            "--taskset-out",
            taskset_path,
            "--out",
            taskset_summary_path,
        ]
        for extra in [str(x) for x in (args.extra_mutation_manifest or []) if str(x).strip()]:
            taskset_argv.extend(["--extra-mutation-manifest", extra])
        taskset_cmd = _run_module("gateforge.agent_modelica_taskset_lock_v1", taskset_argv)

    hard_fail_count = max(0, int(args.inject_hard_fail_count))
    slow_pass_count = max(0, int(args.inject_slow_pass_count))
    inject_enabled = hard_fail_count > 0 or slow_pass_count > 0
    if inject_enabled:
        inject_cmd = _run_module(
            "gateforge.agent_modelica_evidence_stress_injector_v1",
            [
                "--taskset-in",
                taskset_path,
                "--hard-fail-count",
                str(hard_fail_count),
                "--slow-pass-count",
                str(slow_pass_count),
                "--out-taskset",
                injected_taskset_path,
                "--out",
                inject_summary_path,
            ],
        )
        run_taskset_path = injected_taskset_path
    else:
        inject_cmd = {"returncode": 0, "stderr": "", "stdout": "", "module": "inject_disabled", "argv": []}
        run_taskset_path = taskset_path

    run_cmd = _run_module(
        "gateforge.agent_modelica_run_contract_v1",
        [
            "--taskset",
            run_taskset_path,
            "--max-rounds",
            str(max(1, int(args.max_rounds))),
            "--max-time-sec",
            str(max(1, int(args.max_time_sec))),
            "--mode",
            args.run_mode,
            "--runtime-threshold",
            str(float(args.runtime_threshold)),
            "--physics-contract",
            args.physics_contract,
            "--repair-playbook",
            str(args.repair_playbook or ""),
            "--repair-history",
            str(args.repair_history or ""),
            "--focus-queue",
            str(args.focus_queue or ""),
            "--patch-template-adaptations",
            str(args.patch_template_adaptations or ""),
            "--retrieval-policy",
            str(args.retrieval_policy or ""),
            "--live-executor-cmd",
            str(args.live_executor_cmd or ""),
            "--live-timeout-sec",
            str(max(1, int(args.live_timeout_sec))),
            "--live-max-output-chars",
            str(max(200, int(args.live_max_output_chars))),
            "--results-out",
            run_results_path,
            "--out",
            run_summary_path,
        ],
    )

    acceptance_cmd = _run_module(
        "gateforge.agent_modelica_acceptance_gate_v1",
        [
            "--run-results",
            run_results_path,
            "--small-max-time-sec",
            str(max(1, int(args.small_max_time_sec))),
            "--medium-max-time-sec",
            str(max(1, int(args.medium_max_time_sec))),
            "--large-max-time-sec",
            str(max(1, int(args.large_max_time_sec))),
            "--small-max-rounds",
            str(max(1, int(args.small_max_rounds))),
            "--medium-max-rounds",
            str(max(1, int(args.medium_max_rounds))),
            "--large-max-rounds",
            str(max(1, int(args.large_max_rounds))),
            "--out",
            acceptance_path,
        ],
    )

    taskset_summary = _load_json(taskset_summary_path)
    taskset = _load_json(run_taskset_path)
    inject_summary = _load_json(inject_summary_path)
    run_summary = _load_json(run_summary_path)
    run_results_payload = _load_json(run_results_path)
    acceptance_summary = _load_json(acceptance_path)

    tasks = taskset.get("tasks") if isinstance(taskset.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]
    matrix, missing_buckets = _collect_scale_failure_counts(tasks, scales=scales, failure_types=failure_types)
    counts_by_scale, counts_by_failure = _count_scales_and_failures(tasks, scales=scales, failure_types=failure_types)
    missing_scales = [scale for scale, count in counts_by_scale.items() if int(count) <= 0]
    missing_failure_types = [ftype for ftype, count in counts_by_failure.items() if int(count) <= 0]
    layered_pass = _layered_pass_rates(acceptance_summary.get("counts_by_scale", {}), scales=scales)
    run_results = run_results_payload.get("records") if isinstance(run_results_payload.get("records"), list) else []
    run_results = [x for x in run_results if isinstance(x, dict)]
    top_fail_reasons, top_fail_reasons_by_scale_all = _extract_fail_reasons(run_results)
    top_fail_reasons_by_scale = {scale: _top_n(top_fail_reasons_by_scale_all.get(scale, {}), n=3) for scale in scales}

    reasons: list[str] = []
    if taskset_cmd["returncode"] != 0:
        reasons.append("taskset_lock_command_failed")
    if inject_enabled and inject_cmd["returncode"] != 0 and not Path(inject_summary_path).exists():
        reasons.append("stress_injector_command_failed_without_summary")
    if not Path(taskset_path).exists() or not tasks:
        reasons.append("taskset_missing_or_empty")
    if run_cmd["returncode"] != 0 and not Path(run_summary_path).exists():
        reasons.append("run_contract_command_failed_without_summary")
    if acceptance_cmd["returncode"] != 0 and not Path(acceptance_path).exists():
        reasons.append("acceptance_gate_command_failed_without_summary")

    taskset_status = str(taskset_summary.get("status") or "FAIL")
    run_status = str(run_summary.get("status") or "FAIL")
    acceptance_status = str(acceptance_summary.get("status") or "FAIL")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif acceptance_status == "FAIL":
        status = "FAIL"
    elif acceptance_status == "NEEDS_REVIEW" or missing_scales or missing_failure_types:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "taskset_status": taskset_status,
        "taskset_quota_mode": taskset_summary.get("quota_mode"),
        "taskset_coverage_gap": taskset_summary.get("coverage_gap", {}),
        "run_contract_status": run_status,
        "acceptance_status": acceptance_status,
        "total_tasks": int(run_summary.get("total_tasks", 0) or 0),
        "success_at_k_pct": run_summary.get("success_at_k_pct"),
        "median_time_to_pass_sec": run_summary.get("median_time_to_pass_sec"),
        "median_repair_rounds": run_summary.get("median_repair_rounds"),
        "regression_count": int(run_summary.get("regression_count", 0) or 0),
        "physics_fail_count": int(run_summary.get("physics_fail_count", 0) or 0),
        "run_mode": args.run_mode,
        "inject_hard_fail_count": hard_fail_count,
        "inject_slow_pass_count": slow_pass_count,
        "inject_summary": inject_summary if isinstance(inject_summary, dict) else {},
        "runtime_threshold": float(args.runtime_threshold),
        "layered_pass_rate_pct_by_scale": layered_pass,
        "task_count_by_scale": counts_by_scale,
        "task_count_by_failure_type": counts_by_failure,
        "missing_scales": missing_scales,
        "missing_failure_types": missing_failure_types,
        "task_count_matrix_by_scale_failure": matrix,
        "missing_scale_failure_buckets": missing_buckets,
        "scales": scales,
        "failure_types": failure_types,
        "top_fail_reasons": top_fail_reasons,
        "top_fail_reasons_by_scale": top_fail_reasons_by_scale,
        "quota_mode": taskset_summary.get("quota_mode"),
        "coverage_gap": taskset_summary.get("coverage_gap", {}),
        "command_results": {
            "taskset_lock": {
                "returncode": taskset_cmd["returncode"],
                "stderr_tail": str(taskset_cmd.get("stderr") or "").strip().splitlines()[-3:],
            },
            "run_contract": {
                "returncode": run_cmd["returncode"],
                "stderr_tail": str(run_cmd.get("stderr") or "").strip().splitlines()[-3:],
            },
            "stress_injector": {
                "returncode": inject_cmd["returncode"],
                "stderr_tail": str(inject_cmd.get("stderr") or "").strip().splitlines()[-3:],
            },
            "acceptance_gate": {
                "returncode": acceptance_cmd["returncode"],
                "stderr_tail": str(acceptance_cmd.get("stderr") or "").strip().splitlines()[-3:],
            },
        },
        "reasons": reasons,
        "paths": {
            "taskset": taskset_path,
            "taskset_for_run": run_taskset_path,
            "taskset_summary": taskset_summary_path,
            "inject_summary": inject_summary_path if inject_enabled else None,
            "run_results": run_results_path,
            "run_summary": run_summary_path,
            "acceptance_summary": acceptance_path,
        },
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "extra_mutation_manifest": [str(x) for x in (args.extra_mutation_manifest or []) if str(x).strip()],
            "taskset_in": args.taskset_in,
            "physics_contract": args.physics_contract,
            "repair_playbook": args.repair_playbook,
            "repair_history": args.repair_history,
            "focus_queue": args.focus_queue,
            "patch_template_adaptations": args.patch_template_adaptations,
            "retrieval_policy": args.retrieval_policy,
            "live_executor_cmd": args.live_executor_cmd,
            "live_timeout_sec": int(args.live_timeout_sec),
            "live_max_output_chars": int(args.live_max_output_chars),
            "inject_hard_fail_count": hard_fail_count,
            "inject_slow_pass_count": slow_pass_count,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "total_tasks": payload["total_tasks"],
                "success_at_k_pct": payload["success_at_k_pct"],
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
