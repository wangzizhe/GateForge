from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FAILURE_TYPES = ("model_check_error", "simulate_error", "semantic_regression")
DEFAULT_SCALES = ("small", "medium", "large")


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _collect_mutation_rows(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = _load_json(path)
        items = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
        rows.extend([x for x in items if isinstance(x, dict)])
    return rows


def _collect_excluded_mutation_ids(paths: list[str]) -> set[str]:
    out: set[str] = set()
    for path in paths:
        payload = _load_json(path)
        tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            mid = str(task.get("mutation_id") or "").strip()
            if mid:
                out.add(mid)
    return out


def _default_baseline_metrics() -> dict:
    return {
        "steady_state_error": 0.01,
        "overshoot": 0.05,
        "settling_time": 1.0,
        "runtime_seconds": 1.0,
        "events": 10,
    }


def _default_candidate_metrics(ftype: str, baseline: dict) -> dict:
    candidate = dict(baseline)
    if ftype == "semantic_regression":
        candidate["steady_state_error"] = 0.03
    elif ftype == "simulate_error":
        candidate["events"] = 8
    elif ftype == "model_check_error":
        candidate["runtime_seconds"] = 1.2
    return candidate


def _write_json(path: str, payload: object) -> None:
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
    lines = [
        "# GateForge Agent Modelica Holdout Taskset Builder v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- excluded_mutation_ids: `{payload.get('excluded_mutation_id_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build holdout taskset excluding previously used mutation_ids")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--extra-mutation-manifest", action="append", default=[])
    parser.add_argument("--exclude-taskset", action="append", default=[])
    parser.add_argument("--scales", default="small,medium,large")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--max-per-scale-failure-type", type=int, default=4)
    parser.add_argument("--max-per-scale", type=int, default=12)
    parser.add_argument("--taskset-out", default="artifacts/agent_modelica_holdout_taskset_builder_v1/taskset.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_holdout_taskset_builder_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifests = [args.mutation_manifest, *[str(x) for x in (args.extra_mutation_manifest or []) if str(x).strip()]]
    rows = _collect_mutation_rows(manifests)
    excluded_paths = [str(x) for x in (args.exclude_taskset or []) if str(x).strip()]
    excluded_ids = _collect_excluded_mutation_ids(excluded_paths)

    scales = [x.strip().lower() for x in str(args.scales).split(",") if x.strip()]
    if not scales:
        scales = list(DEFAULT_SCALES)
    failure_types = [x.strip().lower() for x in str(args.failure_types).split(",") if x.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)

    max_per_pair = max(1, int(args.max_per_scale_failure_type))
    max_per_scale = max(1, int(args.max_per_scale))
    counts_by_scale = {s: 0 for s in scales}
    counts_by_pair = {s: {f: 0 for f in failure_types} for s in scales}

    selected: list[dict] = []
    skipped_excluded = 0
    sorted_rows = sorted(
        rows,
        key=lambda x: (
            str(x.get("target_scale") or ""),
            str(x.get("expected_failure_type") or ""),
            str(x.get("mutation_id") or ""),
        ),
    )
    for row in sorted_rows:
        scale = str(row.get("target_scale") or "").lower()
        ftype = str(row.get("expected_failure_type") or "").lower()
        if scale not in counts_by_scale or ftype not in failure_types:
            continue
        if counts_by_scale[scale] >= max_per_scale:
            continue
        if counts_by_pair[scale][ftype] >= max_per_pair:
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue
        if mutation_id in excluded_ids:
            skipped_excluded += 1
            continue

        baseline = _default_baseline_metrics()
        selected.append(
            {
                "task_id": f"task_{mutation_id}",
                "scale": scale,
                "failure_type": ftype,
                "mutation_id": mutation_id,
                "source_model_path": str(row.get("source_model_path") or ""),
                "mutated_model_path": str(row.get("mutated_model_path") or ""),
                "repro_command": str(row.get("repro_command") or ""),
                "expected_stage": str(row.get("expected_stage") or ""),
                "mock_success_round": 2,
                "mock_round_duration_sec": 30,
                "baseline_metrics": baseline,
                "candidate_metrics": _default_candidate_metrics(ftype=ftype, baseline=baseline),
            }
        )
        counts_by_scale[scale] += 1
        counts_by_pair[scale][ftype] += 1

    coverage_gaps: list[str] = []
    for scale in scales:
        for ftype in failure_types:
            if int(counts_by_pair[scale][ftype]) <= 0:
                coverage_gaps.append(f"{scale}:{ftype}")

    status = "PASS"
    if not selected:
        status = "FAIL"
    elif coverage_gaps:
        status = "NEEDS_REVIEW"

    taskset_payload = {
        "schema_version": "agent_modelica_taskset_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": selected,
    }
    _write_json(args.taskset_out, taskset_payload)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_tasks": len(selected),
        "excluded_mutation_id_count": len(excluded_ids),
        "skipped_excluded_count": skipped_excluded,
        "scales": scales,
        "failure_types": failure_types,
        "counts_by_scale": counts_by_scale,
        "counts_by_scale_failure_type": counts_by_pair,
        "coverage_gaps": coverage_gaps,
        "taskset_out": args.taskset_out,
        "sources": {
            "mutation_manifest": manifests,
            "exclude_taskset": excluded_paths,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_tasks": len(selected)}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
