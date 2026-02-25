from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .dataset_case import validate_dataset_case


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict | list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _actual_stage_from_failure_type(failure_type: str) -> str:
    ft = str(failure_type or "none")
    if ft in {"none"}:
        return "none"
    if "parse" in ft:
        return "check"
    if "model_check" in ft or "compile" in ft:
        return "check"
    if "simulate" in ft or "solver" in ft or "nan" in ft:
        return "simulate"
    if "regression" in ft or "performance" in ft or "event" in ft:
        return "regress"
    if "review" in ft:
        return "review"
    if "policy" in ft:
        return "policy"
    return "regress"


def _root_cause_from_failure_type(failure_type: str) -> str:
    ft = str(failure_type or "none")
    if ft == "none":
        return "none"
    if "parse" in ft:
        return "parse"
    if "model_check" in ft:
        return "model_check"
    if "simulate" in ft or "solver" in ft:
        return "solver"
    if "nan" in ft or "inf" in ft:
        return "numeric"
    if "invariant" in ft:
        return "invariant"
    if "performance" in ft or "event" in ft:
        return "performance"
    if "drift" in ft:
        return "drift"
    if "policy" in ft or "review" in ft:
        return "governance"
    return "unknown"


def _severity_from_decision(decision: str) -> str:
    if decision == "FAIL":
        return "high"
    if decision == "NEEDS_REVIEW":
        return "medium"
    return "low"


def _case_template(*, case_id: str, source: str, backend: str, model_script: str | None, decision: str, failure_type: str) -> dict:
    stage = _actual_stage_from_failure_type(failure_type)
    return {
        "schema_version": "0.1.0",
        "case_id": case_id,
        "timestamp_utc": _now_utc(),
        "source": source,
        "backend": backend,
        "seed_model": model_script,
        "model_script": model_script,
        "operator": None,
        "intended_stage": "none",
        "intended_failure_type": None,
        "expected_decision": None,
        "actual_stage": stage,
        "actual_failure_type": failure_type,
        "actual_decision": decision,
        "oracle_match": False,
        "replay_stable": True,
        "risk_level": None,
        "factors": {
            "phase": stage,
            "root_cause": _root_cause_from_failure_type(failure_type),
            "trigger": "unknown",
            "severity": _severity_from_decision(decision),
            "determinism": "unknown",
        },
        "artifacts": {},
        "metadata": {},
    }


def adapt_benchmark_summary(summary: dict) -> list[dict]:
    cases: list[dict] = []
    for row in summary.get("cases", []) or []:
        if not isinstance(row, dict):
            continue
        failure_type = str(row.get("failure_type") or "unknown")
        decision = "PASS" if failure_type == "none" else "FAIL"
        name = str(row.get("name") or f"case-{len(cases)}")
        model_script = row.get("script")
        case = _case_template(
            case_id=f"benchmark:{name}",
            source="benchmark",
            backend=str(row.get("backend") or summary.get("backend") or "mock"),
            model_script=model_script if isinstance(model_script, str) else None,
            decision=decision,
            failure_type=failure_type,
        )
        case["oracle_match"] = str(row.get("result") or "FAIL") == "PASS"
        case["factors"]["trigger"] = "baseline"
        case["metadata"] = {
            "pack_id": summary.get("pack_id"),
            "proposal_id": summary.get("proposal_id"),
            "benchmark_result": row.get("result"),
            "mismatches": row.get("mismatches", []),
            "json_path": row.get("json_path"),
        }
        cases.append(case)
    return cases


def adapt_mutation_benchmark_summary(summary: dict) -> list[dict]:
    out = adapt_benchmark_summary(summary)
    for case in out:
        case["source"] = "mutation"
        case["case_id"] = case["case_id"].replace("benchmark:", "mutation:", 1)
        case["factors"]["trigger"] = "mutation_rule"
        case["operator"] = "mutation_rule:unknown"
    return out


def adapt_run_summary(summary: dict, *, source: str = "run") -> dict:
    fail_reasons = summary.get("fail_reasons", []) if isinstance(summary.get("fail_reasons"), list) else []
    primary_reason = str(fail_reasons[0]) if fail_reasons else "none"
    failure_type = "none"
    if summary.get("status") == "FAIL":
        failure_type = primary_reason.split(":", 1)[0] if primary_reason else "unknown"

    decision = str(summary.get("policy_decision") or summary.get("status") or "FAIL")
    if decision == "success":
        decision = "PASS"
    if decision not in {"PASS", "FAIL", "NEEDS_REVIEW"}:
        decision = "FAIL"

    model_script = summary.get("model_script")
    case = _case_template(
        case_id=f"{source}:{summary.get('proposal_id') or 'unknown'}",
        source=source,
        backend=str(summary.get("backend") or "mock"),
        model_script=model_script if isinstance(model_script, str) else None,
        decision=decision,
        failure_type=failure_type,
    )
    case["oracle_match"] = True
    case["risk_level"] = summary.get("risk_level")
    case["factors"]["trigger"] = "llm_plan" if source == "autopilot" else "human_patch"
    case["factors"]["determinism"] = "stable"
    case["metadata"] = {
        "proposal_id": summary.get("proposal_id"),
        "policy_reasons": summary.get("policy_reasons", []),
        "required_human_checks_count": len(summary.get("required_human_checks", []) or []),
        "candidate_path": summary.get("candidate_path"),
        "regression_path": summary.get("regression_path"),
    }
    return case


def validate_cases(cases: list[dict]) -> None:
    for case in cases:
        validate_dataset_case(case)


def main() -> None:
    parser = argparse.ArgumentParser(description="Adapt GateForge summaries into dataset_case rows")
    parser.add_argument(
        "--kind",
        required=True,
        choices=["benchmark", "mutation_benchmark", "run", "autopilot"],
        help="Input summary kind",
    )
    parser.add_argument("--in", dest="input_path", required=True, help="Input summary JSON")
    parser.add_argument("--out", required=True, help="Output dataset case JSON")
    args = parser.parse_args()

    payload = _load_json(args.input_path)
    if args.kind == "benchmark":
        cases = adapt_benchmark_summary(payload)
    elif args.kind == "mutation_benchmark":
        cases = adapt_mutation_benchmark_summary(payload)
    elif args.kind == "run":
        cases = [adapt_run_summary(payload, source="run")]
    else:
        cases = [adapt_run_summary(payload, source="autopilot")]

    validate_cases(cases)
    output: dict | list[dict]
    if args.kind in {"run", "autopilot"}:
        output = cases[0]
    else:
        output = cases
    _write_json(args.out, output)
    print(json.dumps({"kind": args.kind, "count": len(cases), "out": args.out}))


if __name__ == "__main__":
    main()
