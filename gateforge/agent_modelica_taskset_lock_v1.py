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
        "# GateForge Agent Modelica Taskset Lock v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_tasks: `{payload.get('total_tasks')}`",
        f"- scales: `{','.join(payload.get('scales') or [])}`",
        f"- failure_types: `{','.join(payload.get('failure_types') or [])}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lock a scale-layered taskset for Modelica agent workflow evaluation")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--scales", default="small,medium,large")
    parser.add_argument("--failure-types", default=",".join(DEFAULT_FAILURE_TYPES))
    parser.add_argument("--max-per-scale", type=int, default=20)
    parser.add_argument("--max-per-scale-failure-type", type=int, default=0)
    parser.add_argument("--taskset-out", default="artifacts/agent_modelica_taskset_lock_v1/taskset.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_taskset_lock_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    rows = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]

    scales = [x.strip().lower() for x in str(args.scales).split(",") if x.strip()]
    if not scales:
        scales = list(DEFAULT_SCALES)
    failure_types = [x.strip().lower() for x in str(args.failure_types).split(",") if x.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)

    selected: list[dict] = []
    counts_by_scale = {k: 0 for k in scales}
    counts_by_failure = {k: 0 for k in failure_types}
    counts_by_scale_failure = {scale: {ftype: 0 for ftype in failure_types} for scale in scales}
    max_per_scale = max(1, int(args.max_per_scale))
    max_per_scale_failure_type = max(0, int(args.max_per_scale_failure_type))

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
        if scale not in counts_by_scale:
            continue
        if ftype not in counts_by_failure:
            continue
        if counts_by_scale[scale] >= max_per_scale:
            continue
        if max_per_scale_failure_type > 0 and counts_by_scale_failure[scale][ftype] >= max_per_scale_failure_type:
            continue
        mutation_id = str(row.get("mutation_id") or "").strip()
        if not mutation_id:
            continue

        task_id = f"task_{mutation_id}"
        selected.append(
            {
                "task_id": task_id,
                "scale": scale,
                "failure_type": ftype,
                "mutation_id": mutation_id,
                "source_model_path": str(row.get("source_model_path") or ""),
                "mutated_model_path": str(row.get("mutated_model_path") or ""),
                "repro_command": str(row.get("repro_command") or ""),
                "expected_stage": str(row.get("expected_stage") or ""),
                # Lightweight default config for protocol runner.
                "mock_success_round": 2,
                "mock_round_duration_sec": 30,
            }
        )
        counts_by_scale[scale] += 1
        counts_by_failure[ftype] += 1
        counts_by_scale_failure[scale][ftype] += 1

    alerts: list[str] = []
    if not selected:
        alerts.append("taskset_empty")
    for scale in scales:
        if counts_by_scale.get(scale, 0) == 0:
            alerts.append(f"scale_empty:{scale}")

    status = "PASS" if not alerts else "NEEDS_REVIEW"
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
        "scales": scales,
        "failure_types": failure_types,
        "counts_by_scale": counts_by_scale,
        "counts_by_failure_type": counts_by_failure,
        "counts_by_scale_failure_type": counts_by_scale_failure,
        "alerts": alerts,
        "taskset_out": args.taskset_out,
        "sources": {"mutation_manifest": args.mutation_manifest},
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "total_tasks": len(selected)}))
    if status == "NEEDS_REVIEW" and len(selected) == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
