from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_RULES = {
    "model_check_error": [
        "scan undefined symbols and missing declarations",
        "resolve connector/causality mismatches before simulation",
        "rerun checkModel after each localized patch",
    ],
    "simulate_error": [
        "stabilize initialization and start values",
        "bound unstable parameters and solver-sensitive constants",
        "rerun simulate after compile passes",
    ],
    "semantic_regression": [
        "restore sign/unit consistency for dominant components",
        "re-check behavioral metrics against baseline before merge",
        "enforce no-regression guard before final accept",
    ],
}


def _as_actions(rows: list[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        item = str(row or "").strip()
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def recommend_repair_actions_v0(
    *,
    failure_type: str,
    expected_stage: str,
    diagnostic_payload: dict | None = None,
    fallback_actions: list[str] | None = None,
) -> dict:
    ftype = str(failure_type or "").strip().lower()
    stage = str(expected_stage or "").strip().lower()
    diagnostic = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    suggested = [str(x) for x in (diagnostic.get("suggested_actions") or []) if isinstance(x, str)]
    rules = [str(x) for x in (DEFAULT_RULES.get(ftype) or []) if isinstance(x, str)]

    stage_guard: list[str] = []
    if rules or suggested:
        if stage == "check":
            stage_guard.append("do not simulate until checkModel returns pass")
        elif stage == "simulate":
            stage_guard.append("compile/checkModel must pass before any simulate retry")

    deterministic_actions = _as_actions(rules + suggested + stage_guard)
    fallback = _as_actions(fallback_actions or [])

    if deterministic_actions:
        return {
            "channel": "deterministic_rule_policy",
            "actions": deterministic_actions,
            "fallback_used": False,
            "deterministic_action_count": len(deterministic_actions),
            "fallback_action_count": len(fallback),
        }
    return {
        "channel": "fallback_planner_actions",
        "actions": fallback,
        "fallback_used": True,
        "deterministic_action_count": 0,
        "fallback_action_count": len(fallback),
    }


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend repair actions using deterministic policy + fallback")
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--expected-stage", default="")
    parser.add_argument("--diagnostic", default="")
    parser.add_argument("--fallback-actions", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_action_policy_v0/policy.json")
    args = parser.parse_args()

    diagnostic = {}
    if str(args.diagnostic).strip():
        p = Path(str(args.diagnostic))
        if p.exists():
            diagnostic = json.loads(p.read_text(encoding="utf-8"))
    fallback_actions = [x.strip() for x in str(args.fallback_actions or "").split("|") if x.strip()]
    payload = recommend_repair_actions_v0(
        failure_type=str(args.failure_type),
        expected_stage=str(args.expected_stage),
        diagnostic_payload=diagnostic,
        fallback_actions=fallback_actions,
    )
    payload["schema_version"] = "agent_modelica_repair_action_policy_v0"
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(args.out, payload)
    print(json.dumps({"status": "PASS", "channel": payload.get("channel"), "action_count": len(payload.get("actions") or [])}))


if __name__ == "__main__":
    main()
