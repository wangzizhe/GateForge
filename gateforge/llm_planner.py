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


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based planner that emits GateForge intent-file JSON")
    parser.add_argument("--goal", required=True, help="Natural-language planner goal")
    parser.add_argument(
        "--prefer-backend",
        default="auto",
        choices=["auto", "mock", "openmodelica_docker"],
        help="Optional backend preference for intent selection",
    )
    parser.add_argument("--proposal-id", default=None, help="Optional explicit proposal_id")
    parser.add_argument(
        "--out",
        default="artifacts/agent/intent_request.json",
        help="Where to write intent-file JSON",
    )
    args = parser.parse_args()

    intent = _infer_intent(goal=args.goal, prefer_backend=args.prefer_backend)
    payload = {
        "intent": intent,
        "proposal_id": args.proposal_id,
        "overrides": _infer_overrides(args.goal),
        "planner": "rule_v0",
    }
    _write_json(args.out, payload)
    print(json.dumps({"intent": intent, "out": args.out}))


if __name__ == "__main__":
    main()
