from __future__ import annotations

import argparse
import json
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based planner that emits GateForge intent-file JSON")
    parser.add_argument("--goal", default=None, help="Natural-language planner goal")
    parser.add_argument("--goal-file", default=None, help="Path to file containing goal text")
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

    goal_text = _read_goal(goal=args.goal, goal_file=args.goal_file)
    context = _load_context(args.context_json)

    context_prefer_backend = context.get("prefer_backend")
    if context_prefer_backend in {"auto", "mock", "openmodelica_docker"}:
        effective_prefer_backend = context_prefer_backend
    else:
        effective_prefer_backend = args.prefer_backend

    intent = _infer_intent(goal=goal_text, prefer_backend=effective_prefer_backend)
    overrides = _infer_overrides(goal_text)
    if isinstance(context.get("risk_level"), str):
        overrides["risk_level"] = context["risk_level"]
    if isinstance(context.get("change_summary"), str) and context["change_summary"].strip():
        overrides["change_summary"] = context["change_summary"]

    payload = {
        "intent": intent,
        "proposal_id": args.proposal_id,
        "overrides": overrides,
        "planner": "rule_v0",
        "planner_inputs": {
            "goal": goal_text,
            "prefer_backend": effective_prefer_backend,
            "context_path": args.context_json,
        },
        "context": context,
    }
    _write_json(args.out, payload)
    print(json.dumps({"intent": intent, "out": args.out}))


if __name__ == "__main__":
    main()
