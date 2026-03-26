from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_experience_replay_v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _experience_records(payload: dict) -> list[dict]:
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    return [row for row in records if isinstance(row, dict)]


def _action_rows(payload: dict) -> list[tuple[dict, dict]]:
    rows: list[tuple[dict, dict]] = []
    for record in _experience_records(payload):
        actions = record.get("action_contributions") if isinstance(record.get("action_contributions"), list) else []
        for action in actions:
            if isinstance(action, dict):
                rows.append((record, action))
    return rows


def summarize_signal_coverage(
    experience_payload: dict,
    *,
    eligible_trigger_rate_threshold_pct: float = 5.0,
) -> dict:
    action_rows = _action_rows(experience_payload)
    total_action_count = len(action_rows)
    replay_rows = [(record, row) for record, row in action_rows if bool(row.get("replay_eligible"))]
    replay_eligible_action_count = len(replay_rows)
    replay_eligible_rule_ids = sorted({str(row.get("rule_id") or "") for _, row in replay_rows if str(row.get("rule_id") or "").strip()})
    replay_eligible_trigger_rate_pct = round((replay_eligible_action_count / total_action_count) * 100.0, 2) if total_action_count > 0 else 0.0
    status = "sufficient_signal_coverage"
    if replay_eligible_trigger_rate_pct < float(eligible_trigger_rate_threshold_pct):
        status = "insufficient_signal_coverage"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "total_action_count": total_action_count,
        "replay_eligible_action_count": replay_eligible_action_count,
        "replay_eligible_rule_ids": replay_eligible_rule_ids,
        "replay_eligible_trigger_rate_pct": replay_eligible_trigger_rate_pct,
        "eligible_trigger_rate_threshold_pct": float(eligible_trigger_rate_threshold_pct),
        "signal_coverage_status": status,
    }


def build_rule_priority_context(
    experience_payload: dict,
    *,
    failure_type: str,
    error_subtype: str = "",
    min_quality_score: float = 0.6,
) -> dict:
    failure_key = str(failure_type or "").strip()
    subtype_key = str(error_subtype or "").strip()
    stats: dict[str, dict] = {}
    for record, row in _action_rows(experience_payload):
        if not bool(row.get("replay_eligible")):
            continue
        if str(row.get("failure_type") or record.get("failure_type") or "").strip() != failure_key:
            continue
        row_subtype = str(row.get("error_subtype") or record.get("error_subtype") or "").strip()
        if subtype_key and row_subtype and row_subtype != subtype_key:
            continue
        quality_score = float(record.get("repair_quality_score") or row.get("repair_quality_score") or 0.0)
        if quality_score < float(min_quality_score):
            continue
        rule_id = str(row.get("rule_id") or "").strip()
        if not rule_id:
            continue
        slot = stats.setdefault(
            rule_id,
            {
                "rule_id": rule_id,
                "action_key": str(row.get("action_key") or ""),
                "rule_tier": str(row.get("rule_tier") or ""),
                "replay_eligible": bool(row.get("replay_eligible")),
                "sample_count": 0,
                "advancing_count": 0,
                "neutral_count": 0,
                "regressing_count": 0,
                "quality_score_total": 0.0,
                "error_subtype": row_subtype,
            },
        )
        slot["sample_count"] = int(slot.get("sample_count", 0) or 0) + 1
        contribution = str(row.get("contribution") or "").strip().lower()
        if contribution in {"advancing", "neutral", "regressing"}:
            slot[f"{contribution}_count"] = int(slot.get(f"{contribution}_count", 0) or 0) + 1
        slot["quality_score_total"] = float(slot.get("quality_score_total", 0.0) or 0.0) + quality_score

    ranked_rules: list[dict] = []
    for row in stats.values():
        sample_count = int(row.get("sample_count", 0) or 0)
        advancing_count = int(row.get("advancing_count", 0) or 0)
        regressing_count = int(row.get("regressing_count", 0) or 0)
        average_quality_score = round(float(row.get("quality_score_total") or 0.0) / float(sample_count), 4) if sample_count > 0 else 0.0
        advancing_rate = round(advancing_count / float(sample_count), 4) if sample_count > 0 else 0.0
        regressing_rate = round(regressing_count / float(sample_count), 4) if sample_count > 0 else 0.0
        priority_score = round((advancing_rate * 0.7) + (average_quality_score * 0.2) - (regressing_rate * 0.1), 4)
        ranked_row = dict(row)
        ranked_row["average_quality_score"] = average_quality_score
        ranked_row["advancing_rate"] = advancing_rate
        ranked_row["regressing_rate"] = regressing_rate
        ranked_row["priority_score"] = priority_score
        ranked_row.pop("quality_score_total", None)
        ranked_rules.append(ranked_row)

    ranked_rules.sort(
        key=lambda row: (
            -float(row.get("priority_score", 0.0)),
            -int(row.get("sample_count", 0) or 0),
            str(row.get("rule_id") or ""),
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "failure_type": failure_key,
        "error_subtype": subtype_key,
        "min_quality_score": float(min_quality_score),
        "ranked_rules": ranked_rules,
        "recommended_rule_order": [str(row.get("rule_id") or "") for row in ranked_rules if str(row.get("rule_id") or "").strip()],
        "coverage": summarize_signal_coverage(experience_payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build replay coverage and rule-priority context from canonical experience records")
    parser.add_argument("--experience", required=True)
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--error-subtype", default="")
    parser.add_argument("--min-quality-score", type=float, default=0.6)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = _load_json(str(args.experience))
    out = build_rule_priority_context(
        payload,
        failure_type=str(args.failure_type),
        error_subtype=str(args.error_subtype),
        min_quality_score=float(args.min_quality_score),
    )
    _write_json(str(args.out), out)
    print(json.dumps({"status": "PASS", "recommended_rule_order": out.get("recommended_rule_order") or []}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
