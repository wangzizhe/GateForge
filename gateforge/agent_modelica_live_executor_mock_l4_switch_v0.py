import argparse
import json


def _as_bool(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock live executor that passes only when L4 is enabled")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--failure-type", default="model_check_error")
    parser.add_argument("--expected-stage", default="")
    parser.add_argument("--source-model-path", default="")
    parser.add_argument("--mutated-model-path", default="")
    parser.add_argument("--repair-actions", default="")
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--timeout-sec", type=int, default=30)
    parser.add_argument("--backend", default="mock")
    parser.add_argument("--planner-backend", default="rule")
    parser.add_argument("--docker-image", default="")
    parser.add_argument("--l4-enabled", default="0")
    args = parser.parse_args()

    l4_enabled = _as_bool(args.l4_enabled)
    observed_failure_type = "none" if l4_enabled else "model_check_error"
    payload = {
        "task_id": str(args.task_id or "").strip(),
        "failure_type": str(args.failure_type or "model_check_error").strip() or "model_check_error",
        "executor_status": "PASS" if l4_enabled else "FAILED",
        "backend_used": str(args.backend or "mock"),
        "check_model_pass": bool(l4_enabled),
        "simulate_pass": bool(l4_enabled),
        "physics_contract_pass": bool(l4_enabled),
        "regression_pass": bool(l4_enabled),
        "elapsed_sec": 0.05,
        "error_message": "" if l4_enabled else "model check failed",
        "compile_error": "" if l4_enabled else "model check failed",
        "simulate_error_message": "",
        "attempts": [
            {
                "round": 1,
                "check_model_pass": bool(l4_enabled),
                "simulate_pass": bool(l4_enabled),
                "observed_failure_type": observed_failure_type,
                "reason": "mock_l4_switch_pass" if l4_enabled else "compile/syntax error",
                "diagnostic_ir": {
                    "error_type": "none" if l4_enabled else "model_check_error",
                    "error_subtype": "none" if l4_enabled else "parse_lexer_error",
                    "stage": "none" if l4_enabled else "check",
                    "confidence": 0.95,
                },
            }
        ],
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
