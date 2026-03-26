from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_planner_experience_context_v1"
_ALLOWED_RULE_TIERS = {"domain_general_rule", "mutation_contract_rule"}


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


def _estimate_token_count(text: str) -> int:
    raw = str(text or "").strip()
    if not raw:
        return 0
    return max(1, int(math.ceil(len(raw) / 4.0)))


def _experience_records(payload: dict) -> list[dict]:
    records = payload.get("records") if isinstance(payload.get("records"), list) else []
    if not records:
        records = (
            payload.get("experience_records")
            if isinstance(payload.get("experience_records"), list)
            else []
        )
    return [row for row in records if isinstance(row, dict)]


def _action_rows(payload: dict) -> list[tuple[dict, dict]]:
    rows: list[tuple[dict, dict]] = []
    for record in _experience_records(payload):
        actions = (
            record.get("action_contributions")
            if isinstance(record.get("action_contributions"), list)
            else []
        )
        for action in actions:
            if isinstance(action, dict):
                rows.append((record, action))
    return rows


def _action_label(action_key: str, rule_id: str) -> str:
    key = str(action_key or "").strip()
    if "|" in key:
        parts = [part for part in key.split("|") if part]
        if len(parts) >= 2 and str(parts[1]).strip():
            return str(parts[1]).strip()
    rid = str(rule_id or "").strip()
    if rid.startswith("rule_"):
        return rid[len("rule_") :]
    return rid or key or "unknown_action"


def _aggregate_action_stats(
    experience_payload: dict,
    *,
    failure_type: str,
    error_subtype: str = "",
) -> list[dict]:
    failure_key = str(failure_type or "").strip()
    subtype_key = str(error_subtype or "").strip()
    stats: dict[str, dict] = {}
    for record, row in _action_rows(experience_payload):
        row_failure_type = str(
            row.get("failure_type") or record.get("failure_type") or ""
        ).strip()
        if row_failure_type != failure_key:
            continue
        row_subtype = str(
            row.get("error_subtype") or record.get("error_subtype") or ""
        ).strip()
        if subtype_key and row_subtype and row_subtype != subtype_key:
            continue
        rule_tier = str(row.get("rule_tier") or "").strip()
        if rule_tier not in _ALLOWED_RULE_TIERS:
            continue
        action_key = str(row.get("action_key") or "").strip()
        rule_id = str(row.get("rule_id") or "").strip()
        if not action_key and not rule_id:
            continue
        slot_key = action_key or rule_id
        slot = stats.setdefault(
            slot_key,
            {
                "rule_id": rule_id,
                "action_key": action_key,
                "rule_tier": rule_tier,
                "error_subtype": row_subtype,
                "sample_count": 0,
                "advancing_count": 0,
                "neutral_count": 0,
                "regressing_count": 0,
                "quality_score_total": 0.0,
            },
        )
        slot["sample_count"] = int(slot.get("sample_count", 0) or 0) + 1
        contribution = str(row.get("contribution") or "").strip().lower()
        if contribution in {"advancing", "neutral", "regressing"}:
            slot[f"{contribution}_count"] = int(slot.get(f"{contribution}_count", 0) or 0) + 1
        slot["quality_score_total"] = float(slot.get("quality_score_total", 0.0) or 0.0) + float(
            record.get("repair_quality_score") or row.get("repair_quality_score") or 0.0
        )

    aggregated: list[dict] = []
    for row in stats.values():
        sample_count = int(row.get("sample_count", 0) or 0)
        if sample_count <= 0:
            continue
        average_quality_score = round(
            float(row.get("quality_score_total", 0.0) or 0.0) / float(sample_count), 4
        )
        advancing_rate = round(
            int(row.get("advancing_count", 0) or 0) / float(sample_count), 4
        )
        regressing_rate = round(
            int(row.get("regressing_count", 0) or 0) / float(sample_count), 4
        )
        enriched = dict(row)
        enriched["average_quality_score"] = average_quality_score
        enriched["advancing_rate"] = advancing_rate
        enriched["regressing_rate"] = regressing_rate
        enriched["action_label"] = _action_label(
            str(row.get("action_key") or ""), str(row.get("rule_id") or "")
        )
        enriched.pop("quality_score_total", None)
        aggregated.append(enriched)
    return aggregated


def _build_positive_hints(
    aggregated: list[dict],
    *,
    min_quality_score: float,
    max_positive_hints: int,
) -> list[dict]:
    rows = [
        row
        for row in aggregated
        if float(row.get("average_quality_score") or 0.0) >= float(min_quality_score)
        and float(row.get("advancing_rate") or 0.0) > 0.0
    ]
    rows.sort(
        key=lambda row: (
            -float(row.get("advancing_rate") or 0.0),
            -float(row.get("average_quality_score") or 0.0),
            -int(row.get("sample_count") or 0),
            str(row.get("action_key") or row.get("rule_id") or ""),
        )
    )
    selected: list[dict] = []
    for row in rows[: max(0, int(max_positive_hints))]:
        selected.append(
            {
                "rule_id": str(row.get("rule_id") or ""),
                "action_key": str(row.get("action_key") or ""),
                "action_label": str(row.get("action_label") or ""),
                "rule_tier": str(row.get("rule_tier") or ""),
                "sample_count": int(row.get("sample_count") or 0),
                "advancing_rate": float(row.get("advancing_rate") or 0.0),
                "average_quality_score": float(row.get("average_quality_score") or 0.0),
                "message": (
                    f"Historical success: {row.get('action_label')} "
                    f"(rule {row.get('rule_id') or 'unknown'}) advanced similar repairs in "
                    f"{int(row.get('advancing_count') or 0)}/{int(row.get('sample_count') or 0)} "
                    f"cases with avg quality {float(row.get('average_quality_score') or 0.0):.2f}."
                ),
            }
        )
    return selected


def _build_caution_hints(
    aggregated: list[dict],
    *,
    max_negative_hints: int,
) -> list[dict]:
    rows = [
        row
        for row in aggregated
        if float(row.get("regressing_rate") or 0.0) > 0.0
    ]
    rows.sort(
        key=lambda row: (
            -float(row.get("regressing_rate") or 0.0),
            -int(row.get("regressing_count") or 0),
            -int(row.get("sample_count") or 0),
            str(row.get("action_key") or row.get("rule_id") or ""),
        )
    )
    selected: list[dict] = []
    for row in rows[: max(0, int(max_negative_hints))]:
        selected.append(
            {
                "rule_id": str(row.get("rule_id") or ""),
                "action_key": str(row.get("action_key") or ""),
                "action_label": str(row.get("action_label") or ""),
                "rule_tier": str(row.get("rule_tier") or ""),
                "sample_count": int(row.get("sample_count") or 0),
                "regressing_rate": float(row.get("regressing_rate") or 0.0),
                "average_quality_score": float(row.get("average_quality_score") or 0.0),
                "message": (
                    f"Historical caution: {row.get('action_label')} "
                    f"(rule {row.get('rule_id') or 'unknown'}) regressed similar repairs in "
                    f"{int(row.get('regressing_count') or 0)}/{int(row.get('sample_count') or 0)} "
                    f"cases; avoid unless stronger evidence points to it."
                ),
            }
        )
    return selected


def build_planner_experience_context(
    experience_payload: dict,
    *,
    failure_type: str,
    error_subtype: str = "",
    min_quality_score: float = 0.6,
    max_context_tokens: int = 400,
    max_positive_hints: int = 3,
    max_negative_hints: int = 2,
) -> dict:
    aggregated = _aggregate_action_stats(
        experience_payload,
        failure_type=failure_type,
        error_subtype=error_subtype,
    )
    positive_hints = _build_positive_hints(
        aggregated,
        min_quality_score=min_quality_score,
        max_positive_hints=max_positive_hints,
    )
    caution_hints = _build_caution_hints(
        aggregated,
        max_negative_hints=max_negative_hints,
    )

    max_tokens = max(1, int(max_context_tokens))
    lines: list[str] = []
    kept_positive: list[dict] = []
    kept_caution: list[dict] = []
    truncated = False

    if positive_hints or caution_hints:
        header = (
            "Historical experience hints for similar failures "
            "(advisory only; prefer local evidence over memory conflicts):"
        )
        if _estimate_token_count(header) <= max_tokens:
            lines.append(header)

    for hint in positive_hints:
        candidate = lines + [f"- {hint['message']}"]
        if _estimate_token_count("\n".join(candidate)) > max_tokens:
            truncated = True
            break
        lines.append(f"- {hint['message']}")
        kept_positive.append(hint)

    for hint in caution_hints:
        candidate = lines + [f"- {hint['message']}"]
        if _estimate_token_count("\n".join(candidate)) > max_tokens:
            truncated = True
            break
        lines.append(f"- {hint['message']}")
        kept_caution.append(hint)

    prompt_context_text = "\n".join(lines).strip()
    token_estimate = _estimate_token_count(prompt_context_text)
    used = bool(prompt_context_text)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "failure_type": str(failure_type or "").strip(),
        "error_subtype": str(error_subtype or "").strip(),
        "min_quality_score": float(min_quality_score),
        "max_context_tokens": int(max_tokens),
        "positive_hints": kept_positive,
        "caution_hints": kept_caution,
        "positive_hint_count": len(kept_positive),
        "caution_hint_count": len(kept_caution),
        "prompt_context_text": prompt_context_text,
        "prompt_token_estimate": int(token_estimate),
        "used": bool(used),
        "truncated": bool(truncated),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build planner experience injection context from canonical experience records"
    )
    parser.add_argument("--experience", required=True)
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--error-subtype", default="")
    parser.add_argument("--min-quality-score", type=float, default=0.6)
    parser.add_argument("--max-context-tokens", type=int, default=400)
    parser.add_argument("--max-positive-hints", type=int, default=3)
    parser.add_argument("--max-negative-hints", type=int, default=2)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    payload = _load_json(str(args.experience))
    out = build_planner_experience_context(
        payload,
        failure_type=str(args.failure_type),
        error_subtype=str(args.error_subtype),
        min_quality_score=float(args.min_quality_score),
        max_context_tokens=int(args.max_context_tokens),
        max_positive_hints=int(args.max_positive_hints),
        max_negative_hints=int(args.max_negative_hints),
    )
    _write_json(str(args.out), out)
    print(
        json.dumps(
            {
                "status": "PASS",
                "used": bool(out.get("used")),
                "positive_hint_count": int(out.get("positive_hint_count") or 0),
                "caution_hint_count": int(out.get("caution_hint_count") or 0),
                "prompt_token_estimate": int(out.get("prompt_token_estimate") or 0),
                "truncated": bool(out.get("truncated")),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
