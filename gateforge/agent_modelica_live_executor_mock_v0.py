import argparse
import json
from pathlib import Path


def _default_stage(failure_type: str, expected_stage: str) -> str:
    stage = str(expected_stage or "").strip()
    if stage:
        return stage
    normalized = str(failure_type or "").strip().lower()
    if normalized == "simulate_error":
        return "simulate"
    return "check"


def build_payload(task_id: str, failure_type: str, expected_stage: str) -> dict:
    observed_failure_type = str(failure_type or "").strip() or "model_check_error"
    stage = _default_stage(observed_failure_type, expected_stage)
    return {
        "task_id": str(task_id or "").strip(),
        "failure_type": observed_failure_type,
        "executor_status": "PASS",
        "backend_used": "mock",
        "check_model_pass": True,
        "simulate_pass": True,
        "physics_contract_pass": True,
        "regression_pass": True,
        "elapsed_sec": 0.05,
        "attempts": [
            {
                "round": 1,
                "check_model_pass": True,
                "simulate_pass": True,
                "observed_failure_type": observed_failure_type,
                "reason": "mock executor synthesized diagnostic",
                "diagnostic_ir": {
                    "error_type": observed_failure_type,
                    "error_subtype": "mock_ci_signal",
                    "stage": stage,
                    "observed_phase": stage,
                    "confidence": 0.99,
                },
            }
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit deterministic live executor payload for CI and smoke tests")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--failure-type", default="model_check_error")
    parser.add_argument("--expected-stage", default="")
    parser.add_argument("--source-model-path", default="")
    parser.add_argument("--mutated-model-path", default="")
    parser.add_argument("--repair-actions", default="")
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--simulate-stop-time", type=float, default=0.2)
    parser.add_argument("--simulate-intervals", type=int, default=20)
    parser.add_argument("--backend", default="mock")
    parser.add_argument("--docker-image", default="")
    parser.add_argument("--planner-backend", default="rule")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    payload = build_payload(
        task_id=str(args.task_id or ""),
        failure_type=str(args.failure_type or ""),
        expected_stage=str(args.expected_stage or ""),
    )
    payload["backend_used"] = str(args.backend or "mock")
    if str(args.out or "").strip():
        out_path = Path(str(args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
