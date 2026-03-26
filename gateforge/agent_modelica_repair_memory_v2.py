from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_modelica_experience_writer_v1 import build_experience_record


SCHEMA_VERSION = "agent_modelica_repair_memory_v2"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _action_key(action: dict) -> str:
    op = str(action.get("op") or "").strip()
    reason_tag = str(action.get("reason_tag") or "").strip()
    source = str(action.get("source") or "").strip()
    parts = [x for x in [op, reason_tag, source] if x]
    return "|".join(parts) if parts else "unknown"


def _legacy_trajectory_rows_from_record(record: dict) -> list[dict]:
    task_id = str(record.get("task_id") or "")
    rounds = record.get("attempts") if isinstance(record.get("attempts"), list) else []
    rounds = [x for x in rounds if isinstance(x, dict)]
    rows: list[dict] = []
    for idx, attempt in enumerate(rounds):
        l4 = attempt.get("l4") if isinstance(attempt.get("l4"), dict) else {}
        diagnostic = attempt.get("diagnostic_ir") if isinstance(attempt.get("diagnostic_ir"), dict) else {}
        next_failure_type = ""
        if idx + 1 < len(rounds):
            next_failure_type = str(rounds[idx + 1].get("observed_failure_type") or "")
        rows.append(
            {
                "task_id": task_id,
                "round": int(attempt.get("round") or idx + 1),
                "diagnostic_subtype": str(diagnostic.get("error_subtype") or ""),
                "planned_actions": l4.get("planned_actions") if isinstance(l4.get("planned_actions"), list) else [],
                "applied_actions": l4.get("applied_actions") if isinstance(l4.get("applied_actions"), list) else [],
                "hard_check_result": bool(
                    bool(attempt.get("check_model_pass"))
                    and bool(attempt.get("simulate_pass"))
                    and bool(attempt.get("physics_contract_pass"))
                    and bool(attempt.get("regression_pass"))
                ),
                "next_failure_type": next_failure_type,
            }
        )
    return rows


def summarize_action_effectiveness_v2(trajectory_rows: list[dict]) -> list[dict]:
    stats: dict[str, dict[str, Any]] = {}
    for row in trajectory_rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("action_key") or "").strip():
            key = str(row.get("action_key") or "").strip()
            parts = key.split("|")
            op = parts[0] if len(parts) > 0 else ""
            reason_tag = parts[1] if len(parts) > 1 else ""
            source = parts[2] if len(parts) > 2 else ""
            slot = stats.setdefault(
                key,
                {
                    "action_key": key,
                    "op": op,
                    "reason_tag": reason_tag,
                    "source": source,
                    "applied_count": 0,
                    "hard_check_success_count": 0,
                    "advancing_count": 0,
                    "neutral_count": 0,
                    "regressing_count": 0,
                    "high_quality_count": 0,
                    "quality_score_total": 0.0,
                    "replay_eligible": bool(row.get("replay_eligible")),
                    "rule_tier": str(row.get("rule_tier") or ""),
                },
            )
            slot["applied_count"] = int(slot.get("applied_count", 0) or 0) + 1
            contribution = str(row.get("contribution") or "").strip().lower()
            if contribution in {"advancing", "neutral", "regressing"}:
                slot[f"{contribution}_count"] = int(slot.get(f"{contribution}_count", 0) or 0) + 1
            quality_score = float(row.get("repair_quality_score") or 0.0)
            slot["quality_score_total"] = float(slot.get("quality_score_total", 0.0) or 0.0) + quality_score
            if quality_score >= 0.6:
                slot["high_quality_count"] = int(slot.get("high_quality_count", 0) or 0) + 1
            if contribution == "advancing":
                slot["hard_check_success_count"] = int(slot.get("hard_check_success_count", 0) or 0) + 1
            continue

        actions = row.get("applied_actions") if isinstance(row.get("applied_actions"), list) else []
        hard_ok = bool(row.get("hard_check_result"))
        for action in actions:
            if not isinstance(action, dict):
                continue
            key = _action_key(action)
            slot = stats.setdefault(
                key,
                {
                    "action_key": key,
                    "op": str(action.get("op") or ""),
                    "reason_tag": str(action.get("reason_tag") or ""),
                    "source": str(action.get("source") or ""),
                    "applied_count": 0,
                    "hard_check_success_count": 0,
                },
            )
            slot["applied_count"] = int(slot.get("applied_count", 0) or 0) + 1
            if hard_ok:
                slot["hard_check_success_count"] = int(slot.get("hard_check_success_count", 0) or 0) + 1

    rows: list[dict] = []
    for row in stats.values():
        applied = int(row.get("applied_count", 0) or 0)
        success = int(row.get("hard_check_success_count", 0) or 0)
        row["hard_check_success_rate_pct"] = round((success / applied) * 100.0, 2) if applied > 0 else 0.0
        if "quality_score_total" in row:
            row["average_quality_score"] = round(float(row.get("quality_score_total") or 0.0) / float(applied), 4) if applied > 0 else 0.0
            row.pop("quality_score_total", None)
        rows.append(row)
    rows.sort(key=lambda x: (-float(x.get("hard_check_success_rate_pct", 0.0)), -int(x.get("applied_count", 0) or 0), str(x.get("action_key") or "")))
    return rows


def build_repair_memory_v2_from_records(run_results_payload: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    records = run_results_payload.get("records") if isinstance(run_results_payload.get("records"), list) else []
    records = [x for x in records if isinstance(x, dict)]

    trajectory_rows: list[dict] = []
    experience_records: list[dict] = []
    for rec in records:
        experience = build_experience_record(rec)
        experience_records.append(experience)
        action_rows = experience.get("action_contributions") if isinstance(experience.get("action_contributions"), list) else []
        repair_quality_score = float(experience.get("repair_quality_score") or 0.0)
        if action_rows:
            for row in action_rows:
                if not isinstance(row, dict):
                    continue
                enriched = dict(row)
                enriched["repair_quality_score"] = repair_quality_score
                trajectory_rows.append(enriched)
        else:
            trajectory_rows.extend(_legacy_trajectory_rows_from_record(rec))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now,
        "trajectory_rows": trajectory_rows,
        "action_effectiveness": summarize_action_effectiveness_v2(trajectory_rows),
        "experience_records": experience_records,
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build repair memory v2 trajectory summary from run results")
    parser.add_argument("--run-results", required=True)
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_memory_v2/summary.json")
    args = parser.parse_args()

    run_results = _load_json(str(args.run_results))
    payload = build_repair_memory_v2_from_records(run_results)
    payload["sources"] = {"run_results": str(args.run_results)}
    _write_json(str(args.out), payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "trajectory_rows": len(payload.get("trajectory_rows") or []),
                "action_effectiveness_rows": len(payload.get("action_effectiveness") or []),
            }
        )
    )


if __name__ == "__main__":
    main()
