from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .proposal import validate_proposal


def _build_proposal(intent: str, proposal_id: str | None = None) -> dict:
    pid = proposal_id or f"agent-{intent}-{int(time.time())}"
    base = {
        "schema_version": "0.1.0",
        "proposal_id": pid,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "author_type": "agent",
        "change_summary": f"Agent v0 proposal for intent: {intent}",
        "metadata": {
            "agent": "rule_v0",
            "intent": intent,
        },
    }

    if intent == "demo_mock_pass":
        base.update(
            {
                "backend": "mock",
                "model_script": "examples/openmodelica/minimal_probe.mos",
                "requested_actions": ["check", "simulate", "regress"],
                "risk_level": "low",
            }
        )
    elif intent == "demo_openmodelica_pass":
        base.update(
            {
                "backend": "openmodelica_docker",
                "model_script": "examples/openmodelica/minimal_probe.mos",
                "requested_actions": ["check", "simulate", "regress"],
                "risk_level": "low",
            }
        )
    elif intent == "medium_openmodelica_pass":
        base.update(
            {
                "backend": "openmodelica_docker",
                "model_script": "examples/openmodelica/medium_probe.mos",
                "requested_actions": ["check", "simulate", "regress"],
                "risk_level": "medium",
            }
        )
    elif intent == "runtime_regress_low_risk":
        base.update(
            {
                "backend": "mock",
                "model_script": "examples/openmodelica/minimal_probe.mos",
                "requested_actions": ["check", "regress"],
                "risk_level": "low",
            }
        )
    elif intent == "runtime_regress_high_risk":
        base.update(
            {
                "backend": "mock",
                "model_script": "examples/openmodelica/minimal_probe.mos",
                "requested_actions": ["check", "regress"],
                "risk_level": "high",
            }
        )
    else:
        raise ValueError(f"Unsupported intent: {intent}")

    return base


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an agent-authored GateForge proposal")
    parser.add_argument(
        "--intent",
        required=True,
        choices=[
            "demo_mock_pass",
            "demo_openmodelica_pass",
            "medium_openmodelica_pass",
            "runtime_regress_low_risk",
            "runtime_regress_high_risk",
        ],
        help="Agent intent template",
    )
    parser.add_argument(
        "--out",
        default="artifacts/agent_proposal.json",
        help="Where to write proposal JSON",
    )
    parser.add_argument(
        "--proposal-id",
        default=None,
        help="Optional explicit proposal_id",
    )
    args = parser.parse_args()

    proposal = _build_proposal(intent=args.intent, proposal_id=args.proposal_id)
    validate_proposal(proposal)
    _write_json(args.out, proposal)
    print(json.dumps({"proposal_id": proposal["proposal_id"], "intent": args.intent, "out": args.out}))


if __name__ == "__main__":
    main()
