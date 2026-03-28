from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_external_agent_runner_v1 import (
    external_agent_run_schema_v1,
    normalize_external_agent_run,
)


SCHEMA_VERSION = "agent_modelica_track_c_pilot_v0_3_0"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_pilot_v0_3_0"
DEFAULT_BUDGET_RESULTS = (
    "artifacts/agent_modelica_planner_sensitive_eval_v1/results_baseline.json",
    "artifacts/agent_modelica_l4_realism_evidence_v1/main_l5/l4/off/run_results.json",
)


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = max(0.0, min((len(sorted_values) - 1) * q, len(sorted_values) - 1))
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return float(sorted_values[lower])
    weight = index - lower
    return float(sorted_values[lower]) * (1.0 - weight) + float(sorted_values[upper]) * weight


def build_omc_mcp_contract() -> dict:
    return {
        "schema_version": "agent_modelica_omc_mcp_contract_v1",
        "transport": "MCP",
        "tool_count": 4,
        "tools": [
            {
                "name": "omc_check_model",
                "description": "Run OpenModelica checkModel and return compiler diagnostics.",
                "input_schema": {"model_path": "string", "model_name": "string"},
                "output_fields": ["ok", "error_message", "stderr_snippet"],
            },
            {
                "name": "omc_simulate_model",
                "description": "Run OpenModelica simulate and return pass/fail plus runtime diagnostics.",
                "input_schema": {"model_path": "string", "model_name": "string", "stop_time": "number"},
                "output_fields": ["ok", "error_message", "simulation_artifact_path"],
            },
            {
                "name": "omc_get_error_string",
                "description": "Return the latest OMC error string for the active session.",
                "input_schema": {},
                "output_fields": ["error_string"],
            },
            {
                "name": "omc_read_artifact",
                "description": "Read a bounded slice of a generated file or log artifact.",
                "input_schema": {"artifact_path": "string", "max_chars": "integer"},
                "output_fields": ["content", "truncated"],
            },
        ],
    }


def _iter_records(results_path: str) -> list[dict]:
    payload = _load_json(results_path)
    rows = payload.get("records") if isinstance(payload.get("records"), list) else payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def calibrate_budget(results_paths: list[str]) -> dict:
    rounds: list[float] = []
    elapsed: list[float] = []
    sources_used: list[str] = []
    for path in results_paths:
        rows = _iter_records(path)
        if not rows:
            continue
        sources_used.append(str(Path(path).resolve()))
        for row in rows:
            rounds.append(float(row.get("rounds_used") or row.get("agent_rounds") or 0))
            elapsed.append(float(row.get("elapsed_sec") or row.get("wall_clock_sec") or 0.0))
    rounds = sorted([x for x in rounds if x >= 0])
    elapsed = sorted([x for x in elapsed if x >= 0])
    p90_rounds = _quantile(rounds, 0.9)
    p90_elapsed = _quantile(elapsed, 0.9)
    max_agent_rounds = max(3, int(math.ceil(p90_rounds)))
    max_wall_clock_sec = max(90, int(math.ceil(p90_elapsed / 30.0) * 30))
    max_omc_tool_calls = max(6, max_agent_rounds * 2)
    return {
        "schema_version": "agent_modelica_track_c_budget_calibration_v1",
        "sources_used": sources_used,
        "sample_count": len(rounds),
        "rounds_p90": round(p90_rounds, 2),
        "elapsed_sec_p90": round(p90_elapsed, 2),
        "recommended_budget": {
            "max_agent_rounds": max_agent_rounds,
            "max_omc_tool_calls": max_omc_tool_calls,
            "max_wall_clock_sec": max_wall_clock_sec,
        },
        "rationale": "Use GateForge historical P90 on comparable task families to freeze a common operational envelope before external-agent comparison.",
    }


def _prompt_archive() -> dict[str, str]:
    arm1 = "\n".join(
        [
            "You are repairing broken Modelica models.",
            "You may only use the provided OpenModelica MCP tools.",
            "Keep changes minimal and grounded in compiler/runtime feedback.",
            "Return a final answer that includes whether the task passed or failed and why.",
        ]
    )
    arm2 = "\n".join(
        [
            "You are repairing broken Modelica models.",
            "You may only use the provided OpenModelica MCP tools.",
            "Work in short iterations: inspect compiler/runtime feedback, propose one repair, re-check, then decide whether to continue.",
            "Prefer fixes that preserve model structure unless diagnostics force a deeper change.",
            "Return a final answer that includes whether the task passed or failed, the repair rationale, and remaining uncertainty.",
        ]
    )
    return {"arm1_general_agent": arm1, "arm2_frozen_structured_prompt": arm2}


def _prompt_smoke(prompts: dict[str, str]) -> dict:
    checks: list[dict] = []
    status = "PASS"
    for prompt_id, text in prompts.items():
        has_modelica = "Modelica" in text
        has_tools = "MCP" in text or "OpenModelica" in text
        has_output = "Return a final answer" in text
        passed = has_modelica and has_tools and has_output
        checks.append(
            {
                "prompt_id": prompt_id,
                "has_modelica_context": has_modelica,
                "has_tool_constraint": has_tools,
                "has_output_contract": has_output,
                "status": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            status = "FAIL"
    return {"status": status, "checks": checks}


def _mock_external_payload() -> dict:
    return {
        "arm_id": "arm1_general_agent",
        "provider_name": "claude",
        "model_id": "claude-opus-4-6-20260301",
        "model_id_resolvable": True,
        "access_timestamp_utc": "2026-03-28T00:00:00+00:00",
        "prompt_id": "arm1_general_agent",
        "records": [
            {
                "task_id": "smoke_init_case",
                "success": False,
                "task_status": "FAIL",
                "agent_rounds": 2,
                "tool_calls": [{"tool_name": "omc_check_model"}, {"tool_name": "omc_simulate_model"}],
                "wall_clock_sec": 21.4,
                "output_text": "Initialization still fails after two repair attempts.",
            },
            {
                "task_id": "smoke_runtime_case",
                "success": True,
                "task_status": "PASS",
                "agent_rounds": 3,
                "tool_calls": [{"tool_name": "omc_check_model"}, {"tool_name": "omc_simulate_model"}, {"tool_name": "omc_simulate_model"}],
                "wall_clock_sec": 37.8,
                "output_text": "Adjusted unstable parameter regime and simulation passed.",
            },
        ],
    }


def build_track_c_pilot(*, out_dir: str = DEFAULT_OUT_DIR, budget_results_paths: list[str] | None = None) -> dict:
    out_root = Path(out_dir)
    prompts_dir = out_root / "prompts"
    contract = build_omc_mcp_contract()
    schema = external_agent_run_schema_v1()
    budget = calibrate_budget(list(budget_results_paths or list(DEFAULT_BUDGET_RESULTS)))
    prompts = _prompt_archive()
    prompt_smoke = _prompt_smoke(prompts)
    raw_payload = _mock_external_payload()
    normalized = normalize_external_agent_run(raw_payload, source_path=str((out_root / "mock_external_agent_run.json").resolve()))

    _write_json(out_root / "omc_mcp_contract.json", contract)
    _write_json(out_root / "external_agent_run_schema.json", schema)
    _write_json(out_root / "budget_calibration.json", budget)
    for prompt_id, text in prompts.items():
        _write_text(prompts_dir / f"{prompt_id}.md", text)
    _write_json(out_root / "prompt_fairness_smoke.json", prompt_smoke)
    _write_json(out_root / "mock_external_agent_run.json", raw_payload)
    _write_json(out_root / "mock_external_agent_run_normalized.json", normalized)

    status = "PASS" if prompt_smoke.get("status") == "PASS" and int(normalized.get("record_count") or 0) > 0 else "FAIL"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract_path": str((out_root / "omc_mcp_contract.json").resolve()),
        "external_agent_run_schema_path": str((out_root / "external_agent_run_schema.json").resolve()),
        "budget_calibration_path": str((out_root / "budget_calibration.json").resolve()),
        "prompt_fairness_smoke_path": str((out_root / "prompt_fairness_smoke.json").resolve()),
        "normalized_mock_run_path": str((out_root / "mock_external_agent_run_normalized.json").resolve()),
        "recommended_budget": budget.get("recommended_budget"),
        "prompt_smoke_status": prompt_smoke.get("status"),
        "normalized_mock_record_count": int(normalized.get("record_count") or 0),
    }
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# Agent Modelica Track C Pilot v0.3.0",
                "",
                f"- status: `{payload.get('status')}`",
                f"- normalized_mock_record_count: `{payload.get('normalized_mock_record_count')}`",
                f"- prompt_smoke_status: `{payload.get('prompt_smoke_status')}`",
                f"- recommended_budget: `{json.dumps(payload.get('recommended_budget') or {}, ensure_ascii=True)}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Track C pilot substrate for v0.3.0")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--budget-results", action="append", default=[])
    args = parser.parse_args()

    payload = build_track_c_pilot(
        out_dir=str(args.out_dir),
        budget_results_paths=[str(path) for path in (args.budget_results or []) if str(path).strip()] or None,
    )
    print(json.dumps({"status": payload.get("status"), "normalized_mock_record_count": int(payload.get("normalized_mock_record_count") or 0)}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
