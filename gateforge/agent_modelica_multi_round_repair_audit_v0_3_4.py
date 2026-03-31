from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_multi_round_repair_audit_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_multi_round_repair_audit_v0_3_4"
_MULTI_ROUND_FAILURE_TYPES = {
    "cascading_structural_failure",
    "coupled_conflict_failure",
    "false_friend_patch_trap",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _iter_payload_rows(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        for key in ("results", "records", "tasks", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _load_rows_from_input(path: str | Path) -> list[dict]:
    p = Path(path)
    if p.is_dir():
        rows: list[dict] = []
        for child in sorted(p.glob("*.json")):
            rows.extend(_iter_payload_rows(_load_json(child)))
        return rows
    return _iter_payload_rows(_load_json(p))


def _first_attempt_failed(attempts: list[dict]) -> bool:
    if not attempts:
        return False
    first = attempts[0]
    return not bool(first.get("check_model_pass")) or not bool(first.get("simulate_pass"))


def _source_restore_applied(attempts: list[dict]) -> bool:
    for attempt in attempts:
        audit = attempt.get("source_repair")
        if isinstance(audit, dict) and bool(audit.get("applied")):
            return True
    return False


def _multi_round_rule_applied(attempts: list[dict]) -> bool:
    for attempt in attempts:
        audit = attempt.get("multi_round_layered_repair")
        if isinstance(audit, dict) and bool(audit.get("applied")):
            return True
    return False


def _classify_row(row: dict) -> dict:
    failure_type = str(row.get("failure_type") or "").strip().lower()
    attempts = row.get("attempts") if isinstance(row.get("attempts"), list) else []
    executor_status = str(row.get("executor_status") or "")
    resolution_path = str(row.get("resolution_path") or "")
    llm_request_count = int(row.get("live_request_count") or row.get("llm_request_count") or 0)
    rounds_used = int(row.get("rounds_used") or len(attempts))
    final_success = bool(row.get("check_model_pass")) and bool(row.get("simulate_pass")) and executor_status == "PASS"
    source_restore = _source_restore_applied(attempts)
    layered_repair = _multi_round_rule_applied(attempts)
    first_failed = _first_attempt_failed(attempts)
    deterministic_only = resolution_path == "deterministic_rule_only" and llm_request_count == 0
    applicable = failure_type in _MULTI_ROUND_FAILURE_TYPES

    classification = "not_applicable"
    if applicable:
        if final_success and deterministic_only and first_failed and rounds_used >= 2 and (source_restore or layered_repair):
            classification = "deterministic_multi_round_rescue"
        elif final_success:
            classification = "resolved_without_clear_multi_round_rescue_signal"
        else:
            classification = "still_unresolved_multi_round"

    return {
        "task_id": str(row.get("task_id") or ""),
        "failure_type": failure_type,
        "executor_status": executor_status,
        "rounds_used": rounds_used,
        "final_success": final_success,
        "resolution_path": resolution_path,
        "llm_request_count": llm_request_count,
        "source_restore_applied": source_restore,
        "multi_round_rule_applied": layered_repair,
        "first_attempt_failed": first_failed,
        "classification": classification,
    }


def build_multi_round_repair_audit(*, input_path: str, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    rows = [_classify_row(row) for row in _load_rows_from_input(input_path)]
    applicable = [row for row in rows if str(row.get("failure_type") or "") in _MULTI_ROUND_FAILURE_TYPES]
    rescued = [row for row in applicable if row.get("classification") == "deterministic_multi_round_rescue"]
    unresolved = [row for row in applicable if row.get("classification") == "still_unresolved_multi_round"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "input_path": str(Path(input_path).resolve()),
        "input_kind": "directory" if Path(input_path).is_dir() else "file",
        "rows": rows,
        "metrics": {
            "total_rows": len(rows),
            "applicable_multi_round_rows": len(applicable),
            "deterministic_multi_round_rescue_count": len(rescued),
            "still_unresolved_multi_round_count": len(unresolved),
            "deterministic_multi_round_rescue_rate_pct": round((100.0 * len(rescued) / len(applicable)), 2) if applicable else 0.0,
        },
        "recommended_action": (
            "promote_multi_round_deterministic_repair_validation"
            if rescued
            else "collect_more_multi_round_live_evidence"
        ),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# Multi-Round Deterministic Repair Audit v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- applicable_multi_round_rows: `{metrics.get('applicable_multi_round_rows')}`",
        f"- deterministic_multi_round_rescue_count: `{metrics.get('deterministic_multi_round_rescue_count')}`",
        f"- still_unresolved_multi_round_count: `{metrics.get('still_unresolved_multi_round_count')}`",
        f"- recommended_action: `{payload.get('recommended_action')}`",
        "",
        "## Rows",
        "",
    ]
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- `{row.get('task_id')}`: `{row.get('classification')}` "
            f"(failure_type=`{row.get('failure_type')}`, rounds_used=`{row.get('rounds_used')}`)"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit whether multi-round failure cases are being rescued by deterministic repair.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_multi_round_repair_audit(input_path=str(args.input), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "recommended_action": payload.get("recommended_action")}))


if __name__ == "__main__":
    main()
