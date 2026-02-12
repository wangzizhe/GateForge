from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _infer_intent(goal: str, prefer_backend: str) -> str:
    text = goal.lower()
    if "medium" in text or "oscillator" in text:
        return "medium_openmodelica_pass"
    if "high risk" in text or "critical" in text:
        return "runtime_regress_high_risk"
    if "runtime" in text and "regress" in text:
        return "runtime_regress_low_risk"
    if "openmodelica" in text or "docker" in text:
        return "demo_openmodelica_pass"

    if prefer_backend == "openmodelica_docker":
        return "demo_openmodelica_pass"
    return "demo_mock_pass"


def _infer_overrides(goal: str) -> dict:
    text = goal.lower()
    overrides = {"change_summary": goal}
    if "high risk" in text:
        overrides["risk_level"] = "high"
    elif "medium risk" in text:
        overrides["risk_level"] = "medium"
    elif "low risk" in text:
        overrides["risk_level"] = "low"
    return overrides


def _read_goal(goal: str | None, goal_file: str | None) -> str:
    if bool(goal) == bool(goal_file):
        raise ValueError("Exactly one of --goal or --goal-file must be provided")
    if goal is not None:
        return goal
    text = Path(goal_file).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("goal file must contain non-empty text")
    return text


def _load_context(context_json: str | None) -> dict:
    if not context_json:
        return {}
    payload = json.loads(Path(context_json).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("context-json must be a JSON object")
    return payload


def _plan_with_rule_backend(
    *,
    goal_text: str,
    context: dict,
    prefer_backend: str,
    proposal_id: str | None,
    context_json_path: str | None,
) -> dict:
    context_prefer_backend = context.get("prefer_backend")
    if context_prefer_backend in {"auto", "mock", "openmodelica_docker"}:
        effective_prefer_backend = context_prefer_backend
    else:
        effective_prefer_backend = prefer_backend

    intent = _infer_intent(goal=goal_text, prefer_backend=effective_prefer_backend)
    overrides = _infer_overrides(goal_text)
    if isinstance(context.get("risk_level"), str):
        overrides["risk_level"] = context["risk_level"]
    if isinstance(context.get("change_summary"), str) and context["change_summary"].strip():
        overrides["change_summary"] = context["change_summary"]

    return {
        "intent": intent,
        "proposal_id": proposal_id,
        "overrides": overrides,
        "planner": "rule_v0",
        "planner_inputs": {
            "goal": goal_text,
            "prefer_backend": effective_prefer_backend,
            "context_path": context_json_path,
            "planner_backend": "rule",
        },
        "context": context,
    }


def _plan_with_openai_backend_placeholder(
    *,
    goal_text: str,
    context: dict,
    prefer_backend: str,
    proposal_id: str | None,
    context_json_path: str | None,
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("planner-backend=openai requires OPENAI_API_KEY to be set")
    raise ValueError(
        "planner-backend=openai is not implemented yet; keep using --planner-backend rule for now"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based planner that emits GateForge intent-file JSON")
    parser.add_argument("--goal", default=None, help="Natural-language planner goal")
    parser.add_argument("--goal-file", default=None, help="Path to file containing goal text")
    parser.add_argument(
        "--planner-backend",
        default="rule",
        choices=["rule", "openai"],
        help="Planner backend: rule (implemented) or openai (placeholder)",
    )
    parser.add_argument(
        "--prefer-backend",
        default="auto",
        choices=["auto", "mock", "openmodelica_docker"],
        help="Optional backend preference for intent selection",
    )
    parser.add_argument(
        "--context-json",
        default=None,
        help="Optional context JSON path (can provide prefer_backend/risk_level/change_summary)",
    )
    parser.add_argument("--proposal-id", default=None, help="Optional explicit proposal_id")
    parser.add_argument(
        "--out",
        default="artifacts/agent/intent_request.json",
        help="Where to write intent-file JSON",
    )
    args = parser.parse_args()

    try:
        goal_text = _read_goal(goal=args.goal, goal_file=args.goal_file)
        context = _load_context(args.context_json)
        if args.planner_backend == "rule":
            payload = _plan_with_rule_backend(
                goal_text=goal_text,
                context=context,
                prefer_backend=args.prefer_backend,
                proposal_id=args.proposal_id,
                context_json_path=args.context_json,
            )
        else:
            payload = _plan_with_openai_backend_placeholder(
                goal_text=goal_text,
                context=context,
                prefer_backend=args.prefer_backend,
                proposal_id=args.proposal_id,
                context_json_path=args.context_json,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    _write_json(args.out, payload)
    print(json.dumps({"intent": payload["intent"], "out": args.out, "planner_backend": args.planner_backend}))


if __name__ == "__main__":
    main()
