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
        "# GateForge Agent Modelica Taskset Snapshot v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- snapshot_version: `{payload.get('snapshot_version')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- quota_mode: `{payload.get('quota_mode')}`",
        f"- per_scale_target: `{payload.get('per_scale_total_target')}`",
        "",
        "## Counts By Scale",
        "",
    ]
    cbs = payload.get("counts_by_scale", {})
    if isinstance(cbs, dict) and cbs:
        for key in sorted(cbs):
            lines.append(f"- {key}: `{cbs[key]}`")
    else:
        lines.append("- `none`")

    lines.extend(["", "## Missing Targets", ""])
    missing = payload.get("missing_targets", [])
    if isinstance(missing, list) and missing:
        lines.extend([f"- `{x}`" for x in missing])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Coverage Gap", ""])
    coverage_gap = payload.get("coverage_gap", {})
    if isinstance(coverage_gap, dict) and coverage_gap:
        for key in sorted(coverage_gap.keys()):
            lines.append(f"- {key}: `{coverage_gap[key]}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


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


def _collect_rows(paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = _load_json(path)
        muts = payload.get("mutations") if isinstance(payload.get("mutations"), list) else []
        rows.extend([x for x in muts if isinstance(x, dict)])
    return rows


def _make_task(row: dict) -> dict:
    ftype = str(row.get("expected_failure_type") or "unknown").strip().lower()
    baseline = _default_baseline_metrics()
    mutation_id = str(row.get("mutation_id") or "").strip()
    return {
        "task_id": f"task_{mutation_id}",
        "scale": str(row.get("target_scale") or "unknown").strip().lower(),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed-sample taskset snapshot for weekly agent baseline")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--extra-mutation-manifest", action="append", default=[])
    parser.add_argument("--scales", default=",".join(DEFAULT_SCALES))
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--per-scale-total", type=int, default=20)
    parser.add_argument("--per-scale-failure-targets", default="7,7,6")
    parser.add_argument("--adaptive-quota", action="store_true")
    parser.add_argument("--snapshot-version", default=None)
    parser.add_argument("--taskset-out", default="artifacts/agent_modelica_taskset_snapshot_v1/taskset.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_taskset_snapshot_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    scales = [x.strip().lower() for x in str(args.scales).split(",") if x.strip()]
    if not scales:
        scales = list(DEFAULT_SCALES)
    failure_types = [x.strip().lower() for x in str(args.failure_types).split(",") if x.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)

    targets = [int(x.strip()) for x in str(args.per_scale_failure_targets).split(",") if x.strip()]
    if len(targets) != len(failure_types):
        raise SystemExit("--per-scale-failure-targets must match --failure-types length")

    manifest_paths = [args.mutation_manifest, *[str(x) for x in (args.extra_mutation_manifest or []) if str(x).strip()]]
    rows = _collect_rows(manifest_paths)

    buckets: dict[str, dict[str, list[dict]]] = {s: {f: [] for f in failure_types} for s in scales}
    for row in sorted(
        rows,
        key=lambda x: (
            str(x.get("target_scale") or "").lower(),
            str(x.get("expected_failure_type") or "").lower(),
            str(x.get("mutation_id") or ""),
        ),
    ):
        scale = str(row.get("target_scale") or "").strip().lower()
        ftype = str(row.get("expected_failure_type") or "").strip().lower()
        if scale in buckets and ftype in buckets[scale]:
            mid = str(row.get("mutation_id") or "").strip()
            if mid:
                buckets[scale][ftype].append(row)

    target_failure_by_type = {failure_types[idx]: max(0, int(targets[idx])) for idx in range(len(failure_types))}
    effective_failure_by_type = dict(target_failure_by_type)
    if args.adaptive_quota:
        effective_failure_by_type = {}
        for idx, ftype in enumerate(failure_types):
            available_min = min(len(buckets[scale][ftype]) for scale in scales)
            effective_failure_by_type[ftype] = min(max(0, int(targets[idx])), int(available_min))

    selected: list[dict] = []
    counts_by_scale = {s: 0 for s in scales}
    counts_by_scale_failure = {s: {f: 0 for f in failure_types} for s in scales}
    missing_targets: list[str] = []
    per_scale_total = max(1, int(args.per_scale_total))
    effective_per_scale_total = min(per_scale_total, sum(int(effective_failure_by_type.get(f, 0)) for f in failure_types))
    effective_per_scale_total = max(1, effective_per_scale_total)
    quota_mode = "adaptive" if args.adaptive_quota and (
        effective_per_scale_total != per_scale_total or effective_failure_by_type != target_failure_by_type
    ) else "target"

    for scale in scales:
        scale_selected: list[dict] = []
        for idx, ftype in enumerate(failure_types):
            target = int(effective_failure_by_type.get(ftype, 0))
            pool = buckets[scale][ftype]
            picked = pool[:target]
            for row in picked:
                task = _make_task(row)
                scale_selected.append(task)
                counts_by_scale_failure[scale][ftype] += 1
            if len(picked) < target:
                missing_targets.append(f"{scale}:{ftype}:need_{target}_got_{len(picked)}")

        if len(scale_selected) < effective_per_scale_total:
            used_ids = {str(x.get("mutation_id") or "") for x in scale_selected}
            topup_pool: list[dict] = []
            for ftype in failure_types:
                topup_pool.extend([r for r in buckets[scale][ftype] if str(r.get("mutation_id") or "") not in used_ids])
            need = effective_per_scale_total - len(scale_selected)
            for row in topup_pool[:need]:
                task = _make_task(row)
                scale_selected.append(task)
                ftype = str(task.get("failure_type") or "")
                counts_by_scale_failure[scale][ftype] = int(counts_by_scale_failure[scale].get(ftype, 0)) + 1

        if len(scale_selected) < effective_per_scale_total:
            missing_targets.append(f"{scale}:total:need_{effective_per_scale_total}_got_{len(scale_selected)}")

        selected.extend(scale_selected[:effective_per_scale_total])
        counts_by_scale[scale] = len(scale_selected[:effective_per_scale_total])

    snapshot_version = args.snapshot_version or datetime.now(timezone.utc).strftime("snapshot_%Y%m%dT%H%M%SZ")
    taskset_payload = {
        "schema_version": "agent_modelica_taskset_v1",
        "snapshot_version": snapshot_version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks": selected,
    }
    _write_json(args.taskset_out, taskset_payload)

    status = "PASS" if not missing_targets else "NEEDS_REVIEW"
    coverage_gap = {
        "per_scale_total_target": per_scale_total,
        "per_scale_total_effective": effective_per_scale_total,
        "total_tasks_target": per_scale_total * len(scales),
        "total_tasks_effective": len(selected),
        "shortfall_total_tasks": (per_scale_total * len(scales)) - len(selected),
        "failure_targets": target_failure_by_type,
        "failure_effective": effective_failure_by_type,
    }
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "snapshot_version": snapshot_version,
        "total_tasks": len(selected),
        "quota_mode": quota_mode,
        "per_scale_total_target": per_scale_total,
        "per_scale_total_effective": effective_per_scale_total,
        "failure_types": failure_types,
        "scales": scales,
        "failure_targets_by_type": target_failure_by_type,
        "failure_effective_by_type": effective_failure_by_type,
        "coverage_gap": coverage_gap,
        "counts_by_scale": counts_by_scale,
        "counts_by_scale_failure_type": counts_by_scale_failure,
        "missing_targets": missing_targets,
        "taskset_out": args.taskset_out,
        "sources": {
            "mutation_manifest": manifest_paths,
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": status,
                "snapshot_version": snapshot_version,
                "total_tasks": len(selected),
                "quota_mode": quota_mode,
            }
        )
    )


if __name__ == "__main__":
    main()
