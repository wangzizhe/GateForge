from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_external_agent_run_bundle_v1"


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _norm(value: object) -> str:
    return str(value or "").strip()


def external_agent_run_schema_v1() -> dict:
    return {
        "schema_version": "agent_modelica_external_agent_run_schema_v1",
        "bundle_fields": [
            "arm_id",
            "provider_name",
            "model_id",
            "model_id_resolvable",
            "access_timestamp_utc",
            "prompt_id",
            "records",
        ],
        "record_fields": [
            "task_id",
            "success",
            "task_status",
            "infra_failure",
            "infra_failure_reason",
            "budget_exhausted",
            "agent_rounds",
            "omc_tool_call_count",
            "wall_clock_sec",
            "output_text",
        ],
    }


def normalize_external_agent_run(payload: dict, *, source_path: str = "") -> dict:
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    normalized_records: list[dict] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        task_id = _norm(row.get("task_id"))
        if not task_id:
            continue
        success = bool(row.get("success"))
        infra_failure_reason = _norm(row.get("infra_failure_reason"))
        infra_failure = bool(row.get("infra_failure")) or bool(infra_failure_reason)
        task_status = _norm(row.get("task_status"))
        if not task_status:
            task_status = "PASS" if success else "FAIL"
        budget_exhausted = bool(row.get("budget_exhausted")) or task_status == "BUDGET_EXHAUSTED"
        tool_calls = row.get("tool_calls") if isinstance(row.get("tool_calls"), list) else []
        omc_tool_call_count = int(row.get("omc_tool_call_count") or len(tool_calls) or 0)
        agent_rounds = int(row.get("agent_rounds") or row.get("rounds_used") or 0)
        wall_clock_sec = float(row.get("wall_clock_sec") or row.get("elapsed_sec") or 0.0)
        normalized_records.append(
            {
                "task_id": task_id,
                "success": success,
                "task_status": task_status,
                "infra_failure": infra_failure,
                "infra_failure_reason": infra_failure_reason,
                "budget_exhausted": budget_exhausted,
                "agent_rounds": max(0, agent_rounds),
                "omc_tool_call_count": max(0, omc_tool_call_count),
                "wall_clock_sec": round(max(0.0, wall_clock_sec), 2),
                "output_text": _norm(row.get("output_text")),
            }
        )
    success_count = len([row for row in normalized_records if bool(row.get("success"))])
    infra_failure_count = len([row for row in normalized_records if bool(row.get("infra_failure"))])
    budget_exhausted_count = len([row for row in normalized_records if bool(row.get("budget_exhausted"))])
    total_rounds = sum(int(row.get("agent_rounds") or 0) for row in normalized_records)
    total_tool_calls = sum(int(row.get("omc_tool_call_count") or 0) for row in normalized_records)
    total_wall_clock = sum(float(row.get("wall_clock_sec") or 0.0) for row in normalized_records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": source_path,
        "arm_id": _norm(payload.get("arm_id") or "arm_unknown"),
        "provider_name": _norm(payload.get("provider_name") or "unknown_provider"),
        "model_id": _norm(payload.get("model_id") or "unknown_model"),
        "model_id_resolvable": bool(payload.get("model_id_resolvable")),
        "access_timestamp_utc": _norm(payload.get("access_timestamp_utc")) or datetime.now(timezone.utc).isoformat(),
        "prompt_id": _norm(payload.get("prompt_id")),
        "record_count": len(normalized_records),
        "records": normalized_records,
        "summary": {
            "success_count": success_count,
            "success_rate_pct": _ratio(success_count, len(normalized_records)),
            "infra_failure_count": infra_failure_count,
            "budget_exhausted_count": budget_exhausted_count,
            "avg_agent_rounds": round((total_rounds / len(normalized_records)), 2) if normalized_records else 0.0,
            "avg_omc_tool_call_count": round((total_tool_calls / len(normalized_records)), 2) if normalized_records else 0.0,
            "avg_wall_clock_sec": round((total_wall_clock / len(normalized_records)), 2) if normalized_records else 0.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize external-agent runs into the Track C run contract")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = _load_json(args.input)
    normalized = normalize_external_agent_run(payload, source_path=str(Path(args.input).resolve()))
    _write_json(args.out, normalized)
    print(json.dumps({"status": "PASS", "record_count": int(normalized.get("record_count") or 0)}))


if __name__ == "__main__":
    main()
