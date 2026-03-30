from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_external_agent_runner_v1 import normalize_external_agent_run


SCHEMA_VERSION = "agent_modelica_track_c_matrix_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_matrix_v0_3_2"


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


def _norm(value: object) -> str:
    return str(value or "").strip()


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _task_ids_from_taskset(path: str | Path) -> list[str]:
    payload = _load_json(path)
    rows = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
    return [_norm(row.get("task_id")) for row in rows if isinstance(row, dict) and _norm(row.get("task_id"))]


def build_gateforge_bundle_from_results_paths(
    *,
    taskset_path: str,
    results_paths: list[str],
    out_path: str,
    arm_id: str = "gateforge_authority",
    model_id: str = "gateforge-v0.3.2/authority",
) -> dict:
    task_ids = _task_ids_from_taskset(taskset_path)
    task_id_set = set(task_ids)
    by_task_id: dict[str, dict] = {}
    source_path_by_task_id: dict[str, str] = {}
    for path in results_paths:
        payload = _load_json(path)
        rows = payload.get("results") if isinstance(payload.get("results"), list) else payload.get("records") if isinstance(payload.get("records"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            task_id = _norm(row.get("task_id") or row.get("mutation_id"))
            if not task_id or task_id not in task_id_set or task_id in by_task_id:
                continue
            by_task_id[task_id] = row
            source_path_by_task_id[task_id] = str(path)

    raw_records: list[dict] = []
    for task_id in task_ids:
        row = by_task_id.get(task_id)
        if row is None:
            raw_records.append(
                {
                    "task_id": task_id,
                    "success": False,
                    "task_status": "FAIL",
                    "infra_failure": False,
                    "infra_failure_reason": "",
                    "budget_exhausted": False,
                    "agent_rounds": 0,
                    "omc_tool_call_count": 0,
                    "wall_clock_sec": 0.0,
                    "output_text": "missing_gateforge_authority_result",
                    "source_results_path": "",
                }
            )
            continue
        passed = bool(row.get("passed")) or bool(row.get("success"))
        raw_records.append(
            {
                "task_id": task_id,
                "success": passed,
                "task_status": "PASS" if passed else "FAIL",
                "infra_failure": False,
                "infra_failure_reason": "",
                "budget_exhausted": False,
                "agent_rounds": int(row.get("rounds_used") or 0),
                "omc_tool_call_count": 0,
                "wall_clock_sec": float(row.get("elapsed_sec") or row.get("time_to_pass_sec") or 0.0),
                "output_text": _norm(
                    row.get("resolution_path")
                    or row.get("current_fail_bucket")
                    or row.get("error")
                    or row.get("failure_type")
                ),
                "source_results_path": source_path_by_task_id.get(task_id, ""),
            }
        )

    raw_bundle = {
        "arm_id": str(arm_id),
        "provider_name": "gateforge",
        "model_id": str(model_id),
        "model_id_resolvable": True,
        "access_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_id": str(arm_id),
        "records": raw_records,
    }
    normalized = normalize_external_agent_run(raw_bundle, source_path=str(Path(taskset_path).resolve()))
    _write_json(out_path, normalized)
    return normalized


def _iter_bundle_rows(bundle_paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for path in bundle_paths:
        payload = _load_json(path)
        if payload:
            rows.append(payload)
    return rows


def _infra_normalized_success_rate(bundle: dict) -> float:
    rows = bundle.get("records") if isinstance(bundle.get("records"), list) else []
    valid = [row for row in rows if isinstance(row, dict) and not bool(row.get("infra_failure"))]
    if not valid:
        return 0.0
    success = len([row for row in valid if bool(row.get("success"))])
    return _ratio(success, len(valid))


def summarize_track_c_matrix(*, bundle_paths: list[str], out_dir: str = DEFAULT_OUT_DIR) -> dict:
    bundles = _iter_bundle_rows(bundle_paths)
    grouped_rows: list[dict] = []
    by_key: dict[tuple[str, str, str], list[dict]] = {}
    for bundle in bundles:
        summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
        row = {
            "provider_name": _norm(bundle.get("provider_name")),
            "arm_id": _norm(bundle.get("arm_id")),
            "model_id": _norm(bundle.get("model_id")),
            "record_count": int(bundle.get("record_count") or 0),
            "success_rate_pct": float(summary.get("success_rate_pct") or 0.0),
            "infra_failure_count": int(summary.get("infra_failure_count") or 0),
            "infra_failure_rate_pct": _ratio(int(summary.get("infra_failure_count") or 0), int(bundle.get("record_count") or 0)),
            "infra_normalized_success_rate_pct": _infra_normalized_success_rate(bundle),
            "source_bundle_path": _norm(bundle.get("source_path")),
        }
        grouped_rows.append(row)
        by_key.setdefault((row["provider_name"], row["arm_id"], row["model_id"]), []).append(row)

    variance_rows: list[dict] = []
    for (provider_name, arm_id, model_id), rows in sorted(by_key.items()):
        values = [float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in rows]
        infra_values = [float(row.get("infra_failure_rate_pct") or 0.0) for row in rows]
        variance_rows.append(
            {
                "provider_name": provider_name,
                "arm_id": arm_id,
                "model_id": model_id,
                "run_count": len(rows),
                "mean_infra_normalized_success_rate_pct": _mean(values),
                "min_success_rate_pct": min(values) if values else 0.0,
                "max_success_rate_pct": max(values) if values else 0.0,
                "spread_pct": round((max(values) - min(values)), 2) if values else 0.0,
                "mean_infra_failure_rate_pct": _mean(infra_values),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if bundles else "FAIL",
        "bundle_paths": [str(Path(path).resolve()) if Path(path).exists() else str(path) for path in bundle_paths],
        "grouped_rows": grouped_rows,
        "variance_summary": variance_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "variance_summary.json", {"rows": variance_rows})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize repeated Track C normalized bundles for v0.3.2.")
    parser.add_argument("--bundle", action="append", default=[])
    parser.add_argument("--gateforge-taskset", default="")
    parser.add_argument("--gateforge-results", action="append", default=[])
    parser.add_argument("--gateforge-out-path", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    bundle_paths = [str(x) for x in (args.bundle or []) if str(x).strip()]
    if _norm(args.gateforge_taskset) and args.gateforge_results:
        gateforge_out = _norm(args.gateforge_out_path) or str(Path(args.out_dir) / "gateforge_authority_bundle.json")
        build_gateforge_bundle_from_results_paths(
            taskset_path=str(args.gateforge_taskset),
            results_paths=[str(x) for x in (args.gateforge_results or []) if str(x).strip()],
            out_path=gateforge_out,
        )
        bundle_paths.append(gateforge_out)

    payload = summarize_track_c_matrix(bundle_paths=bundle_paths, out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "bundle_count": len(payload.get("bundle_paths") or [])}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
