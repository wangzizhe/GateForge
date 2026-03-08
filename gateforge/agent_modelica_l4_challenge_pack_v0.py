from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_l4_challenge_pack_v0"
DEFAULT_FAILURE_TYPES = ("model_check_error", "simulate_error", "semantic_regression")
DEFAULT_SCALES = ("small", "medium")


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
        "# Agent Modelica L4 Challenge Pack v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_selected_tasks: `{payload.get('total_selected_tasks')}`",
        f"- per_failure_type_quota: `{payload.get('per_failure_type_quota')}`",
        f"- baseline_off_success_at_k_pct: `{payload.get('baseline_off_success_at_k_pct')}`",
        f"- baseline_target_range_pct: `{payload.get('baseline_target_range_pct')}`",
        f"- baseline_in_target_range: `{payload.get('baseline_in_target_range')}`",
        f"- reasons: `{payload.get('reasons')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _task_sort_key(task: dict) -> tuple[str, str, str]:
    return (
        _norm(task.get("task_id")).lower(),
        _norm(task.get("mutated_model_path")).lower(),
        _norm(task.get("source_model_path")).lower(),
    )


def _task_key_for_split(task: dict, seed: str) -> str:
    parts = [
        seed,
        _norm(task.get("task_id")).lower(),
        _norm(task.get("failure_type")).lower(),
        _norm(task.get("scale")).lower(),
        _norm(task.get("mutated_model_path")).lower(),
    ]
    return "|".join(parts)


def _assign_split(task: dict, holdout_ratio: float, seed: str) -> str:
    digest = hashlib.sha256(_task_key_for_split(task, seed=seed).encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 10000
    threshold = int(max(0.0, min(1.0, float(holdout_ratio))) * 10000)
    return "holdout" if bucket < threshold else "train"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def _parse_csv(raw: str, default: tuple[str, ...]) -> list[str]:
    rows = [str(x).strip() for x in str(raw or "").split(",") if str(x).strip()]
    return rows if rows else list(default)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic Electrical challenge pack for L4 uplift evaluation")
    parser.add_argument("--taskset-in", required=True)
    parser.add_argument("--out-dir", default="assets_private/agent_modelica_l4_challenge_pack_v0")
    parser.add_argument("--scales", default="small,medium")
    parser.add_argument("--failure-types", default="model_check_error,simulate_error,semantic_regression")
    parser.add_argument("--per-failure-type-cap", type=int, default=6)
    parser.add_argument("--holdout-ratio", type=float, default=0.15)
    parser.add_argument("--split-seed", default="agent_modelica_l4_challenge_v0")
    parser.add_argument("--baseline-off-success-at-k-pct", type=float, default=None)
    parser.add_argument("--target-min-off-success-pct", type=float, default=60.0)
    parser.add_argument("--target-max-off-success-pct", type=float, default=90.0)
    parser.add_argument("--out", default="")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    scales = [x.lower() for x in _parse_csv(args.scales, DEFAULT_SCALES)]
    failure_types = [x.lower() for x in _parse_csv(args.failure_types, DEFAULT_FAILURE_TYPES)]
    per_failure_type_cap = max(1, int(args.per_failure_type_cap))

    payload = _load_json(args.taskset_in)
    tasks = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    tasks = [x for x in tasks if isinstance(x, dict)]

    filtered = []
    for task in tasks:
        scale = _norm(task.get("scale")).lower()
        failure_type = _norm(task.get("failure_type")).lower()
        if scale not in scales:
            continue
        if failure_type not in failure_types:
            continue
        filtered.append(dict(task))

    grouped: dict[str, list[dict]] = {f: [] for f in failure_types}
    for task in filtered:
        grouped[_norm(task.get("failure_type")).lower()].append(task)
    for key in grouped:
        grouped[key] = sorted(grouped[key], key=_task_sort_key)

    non_empty_counts = [len(grouped[f]) for f in failure_types]
    quota = min([per_failure_type_cap] + non_empty_counts) if non_empty_counts else 0

    selected: list[dict] = []
    for failure_type in failure_types:
        selected.extend(grouped[failure_type][:quota])
    selected = sorted(selected, key=_task_sort_key)

    for task in selected:
        task["split"] = _assign_split(task=task, holdout_ratio=float(args.holdout_ratio), seed=str(args.split_seed))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    taskset_unfrozen_path = out_dir / "taskset_unfrozen.json"
    taskset_frozen_path = out_dir / "taskset_frozen.json"
    selection_config_path = out_dir / "selection_config.json"
    manifest_path = out_dir / "manifest.json"
    sha_path = out_dir / "sha256.json"
    summary_path = Path(args.out or (out_dir / "frozen_summary.json"))

    taskset_unfrozen_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "challenge_pack_unfrozen",
        "tasks": selected,
        "sources": {"taskset_in": str(args.taskset_in)},
    }
    taskset_frozen_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "challenge_pack_frozen",
        "tasks": selected,
        "sources": {"taskset_in": str(args.taskset_in)},
        "split_freeze": {
            "schema_version": "agent_modelica_taskset_split_freeze_v1",
            "seed": str(args.split_seed),
            "holdout_ratio": float(args.holdout_ratio),
        },
    }
    selection_config = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scales": scales,
        "failure_types": failure_types,
        "per_failure_type_cap": per_failure_type_cap,
        "effective_per_failure_type_quota": quota,
        "split_seed": str(args.split_seed),
        "holdout_ratio": float(args.holdout_ratio),
        "baseline_target_range_pct": {
            "min": float(args.target_min_off_success_pct),
            "max": float(args.target_max_off_success_pct),
        },
    }

    _write_json(str(taskset_unfrozen_path), taskset_unfrozen_payload)
    _write_json(str(taskset_frozen_path), taskset_frozen_payload)
    _write_json(str(selection_config_path), selection_config)

    sha_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "taskset_unfrozen": _sha256(taskset_unfrozen_path),
        "taskset_frozen": _sha256(taskset_frozen_path),
        "selection_config": _sha256(selection_config_path),
    }
    _write_json(str(sha_path), sha_payload)

    by_scale: dict[str, int] = {}
    by_failure: dict[str, int] = {}
    split_counts = {"train": 0, "holdout": 0}
    for task in selected:
        scale = _norm(task.get("scale")).lower()
        failure_type = _norm(task.get("failure_type")).lower()
        split = _norm(task.get("split")).lower()
        by_scale[scale] = int(by_scale.get(scale, 0)) + 1
        by_failure[failure_type] = int(by_failure.get(failure_type, 0)) + 1
        if split in split_counts:
            split_counts[split] += 1

    baseline = args.baseline_off_success_at_k_pct if args.baseline_off_success_at_k_pct is not None else None
    baseline_in_range = False
    reasons: list[str] = []
    if not selected:
        reasons.append("taskset_empty_after_selection")
    if quota <= 0:
        reasons.append("quota_zero")
    if baseline is None:
        reasons.append("baseline_off_success_at_k_missing")
    else:
        baseline_in_range = float(args.target_min_off_success_pct) <= float(baseline) <= float(args.target_max_off_success_pct)
        if not baseline_in_range:
            reasons.append("baseline_off_success_out_of_target_range")

    status = "PASS" if not reasons else ("NEEDS_REVIEW" if reasons == ["baseline_off_success_at_k_missing"] else "FAIL")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "taskset_in": str(args.taskset_in),
        "counts": {
            "total_selected_tasks": len(selected),
            "counts_by_scale": by_scale,
            "counts_by_failure_type": by_failure,
            "split_counts": split_counts,
        },
        "selection": selection_config,
        "baseline_off_success_at_k_pct": baseline,
        "baseline_target_range_pct": {"min": float(args.target_min_off_success_pct), "max": float(args.target_max_off_success_pct)},
        "baseline_in_target_range": baseline_in_range if baseline is not None else None,
        "files": {
            "taskset_unfrozen": str(taskset_unfrozen_path),
            "taskset_frozen": str(taskset_frozen_path),
            "selection_config": str(selection_config_path),
            "sha256": str(sha_path),
        },
        "sha256": sha_payload,
        "reasons": reasons,
    }
    _write_json(str(manifest_path), manifest)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_selected_tasks": len(selected),
        "per_failure_type_quota": quota,
        "baseline_off_success_at_k_pct": baseline,
        "baseline_target_range_pct": {"min": float(args.target_min_off_success_pct), "max": float(args.target_max_off_success_pct)},
        "baseline_in_target_range": baseline_in_range if baseline is not None else None,
        "manifest_path": str(manifest_path),
        "taskset_frozen_path": str(taskset_frozen_path),
        "reasons": reasons,
    }
    _write_json(str(summary_path), summary)
    _write_markdown(args.report_out or _default_md_path(str(summary_path)), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "total_selected_tasks": summary.get("total_selected_tasks"),
                "baseline_off_success_at_k_pct": summary.get("baseline_off_success_at_k_pct"),
                "baseline_in_target_range": summary.get("baseline_in_target_range"),
            }
        )
    )
    if str(summary.get("status")) == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
