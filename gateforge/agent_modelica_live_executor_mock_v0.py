import argparse
import json
from pathlib import Path


def _load_fixture(path: str) -> dict:
    text = str(path or "").strip()
    if not text:
        return {}
    fixture_path = Path(text)
    if not fixture_path.exists():
        return {}
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _default_stage(failure_type: str, expected_stage: str) -> str:
    stage = str(expected_stage or "").strip()
    if stage:
        return stage
    normalized = str(failure_type or "").strip().lower()
    if normalized == "simulate_error":
        return "simulate"
    return "check"


def build_payload(task_id: str, failure_type: str, expected_stage: str, *, fixture: dict | None = None) -> dict:
    fixture_payload = fixture if isinstance(fixture, dict) else {}
    observed_failure_type = str(failure_type or "").strip() or "model_check_error"
    stage = _default_stage(observed_failure_type, expected_stage)
    diagnostic = fixture_payload.get("diagnostic_ir") if isinstance(fixture_payload.get("diagnostic_ir"), dict) else {}
    signal_values = fixture_payload.get("signal_values") if isinstance(fixture_payload.get("signal_values"), dict) else {}
    produced_artifacts = [
        str(item)
        for item in (fixture_payload.get("produced_artifacts") or [])
        if str(item or "").strip()
    ]
    reason = str(fixture_payload.get("reason") or "mock executor synthesized diagnostic")
    return {
        "task_id": str(task_id or "").strip(),
        "failure_type": observed_failure_type,
        "executor_status": "PASS",
        "backend_used": "mock",
        "check_model_pass": bool(fixture_payload.get("check_model_pass", True)),
        "simulate_pass": bool(fixture_payload.get("simulate_pass", True)),
        "physics_contract_pass": bool(fixture_payload.get("physics_contract_pass", True)),
        "regression_pass": bool(fixture_payload.get("regression_pass", True)),
        "elapsed_sec": float(fixture_payload.get("elapsed_sec", 0.05) or 0.05),
        "signal_values": signal_values,
        "produced_artifacts": produced_artifacts,
        "attempts": [
            {
                "round": 1,
                "check_model_pass": bool(fixture_payload.get("check_model_pass", True)),
                "simulate_pass": bool(fixture_payload.get("simulate_pass", True)),
                "observed_failure_type": str(fixture_payload.get("observed_failure_type") or observed_failure_type),
                "reason": reason,
                "diagnostic_ir": {
                    "error_type": str(diagnostic.get("error_type") or observed_failure_type),
                    "error_subtype": str(diagnostic.get("error_subtype") or "mock_ci_signal"),
                    "stage": str(diagnostic.get("stage") or stage),
                    "observed_phase": str(diagnostic.get("observed_phase") or stage),
                    "confidence": float(diagnostic.get("confidence", 0.99) or 0.99),
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
    parser.add_argument("--fixture-path", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    payload = build_payload(
        task_id=str(args.task_id or ""),
        failure_type=str(args.failure_type or ""),
        expected_stage=str(args.expected_stage or ""),
        fixture=_load_fixture(str(args.fixture_path or "")),
    )
    payload["backend_used"] = str(args.backend or "mock")
    if str(args.out or "").strip():
        out_path = Path(str(args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
