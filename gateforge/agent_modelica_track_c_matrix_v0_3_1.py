from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_external_agent_runner_v1 import normalize_external_agent_run


SCHEMA_VERSION = "agent_modelica_track_c_matrix_v0_3_1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_matrix_v0_3_1"


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


def build_gateforge_bundle_from_results(
    *,
    results_path: str,
    out_path: str,
    arm_id: str = "gateforge_full",
    model_id: str = "gateforge-v0.3.1/auto",
) -> dict:
    payload = _load_json(results_path)
    rows = payload.get("results") if isinstance(payload.get("results"), list) else []
    raw = {
        "arm_id": str(arm_id),
        "provider_name": "gateforge",
        "model_id": str(model_id),
        "model_id_resolvable": True,
        "access_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt_id": str(arm_id),
        "records": [
            {
                "task_id": _norm(row.get("mutation_id")),
                "success": bool(row.get("success")),
                "task_status": "PASS" if bool(row.get("success")) else "FAIL",
                "infra_failure": False,
                "infra_failure_reason": "",
                "budget_exhausted": False,
                "agent_rounds": int(row.get("rounds_used") or 0),
                "omc_tool_call_count": 0,
                "wall_clock_sec": float(row.get("elapsed_sec") or 0.0),
                "output_text": _norm(row.get("resolution_path") or row.get("error")),
            }
            for row in rows
            if isinstance(row, dict) and _norm(row.get("mutation_id"))
        ],
    }
    normalized = normalize_external_agent_run(raw, source_path=str(Path(results_path).resolve()))
    _write_json(out_path, normalized)
    return normalized


def _iter_bundle_rows(bundle_paths: list[str]) -> list[dict]:
    rows: list[dict] = []
    for path in bundle_paths:
        payload = _load_json(path)
        if not payload:
            continue
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
    grouped: list[dict] = []
    for bundle in bundles:
        summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
        grouped.append(
            {
                "provider_name": _norm(bundle.get("provider_name")),
                "arm_id": _norm(bundle.get("arm_id")),
                "model_id": _norm(bundle.get("model_id")),
                "record_count": int(bundle.get("record_count") or 0),
                "success_rate_pct": float(summary.get("success_rate_pct") or 0.0),
                "infra_failure_rate_pct": _ratio(int(summary.get("infra_failure_count") or 0), int(bundle.get("record_count") or 0)),
                "infra_normalized_success_rate_pct": _infra_normalized_success_rate(bundle),
            }
        )

    variance_rows: list[dict] = []
    by_key: dict[tuple[str, str, str], list[dict]] = {}
    for row in grouped:
        key = (row["provider_name"], row["arm_id"], row["model_id"])
        by_key.setdefault(key, []).append(row)
    for (provider_name, arm_id, model_id), rows in sorted(by_key.items()):
        values = [float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in rows]
        variance_rows.append(
            {
                "provider_name": provider_name,
                "arm_id": arm_id,
                "model_id": model_id,
                "run_count": len(rows),
                "min_success_rate_pct": min(values) if values else 0.0,
                "max_success_rate_pct": max(values) if values else 0.0,
                "spread_pct": round((max(values) - min(values)), 2) if values else 0.0,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if bundles else "FAIL",
        "bundle_paths": [str(Path(path).resolve()) if Path(path).exists() else str(path) for path in bundle_paths],
        "grouped_rows": grouped,
        "variance_summary": variance_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "variance_summary.json", {"rows": variance_rows})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize repeated Track C normalized bundles for v0.3.1.")
    parser.add_argument("--bundle", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = summarize_track_c_matrix(bundle_paths=[str(x) for x in (args.bundle or []) if str(x).strip()], out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "bundle_count": len(payload.get("bundle_paths") or [])}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
