"""
Strip legacy stage/search/replan fields from benchmark_trajectory_gf_v1_v0_19_16
raw JSON files.

The transparent repair loop (v0.19.16) only writes a small set of meaningful
fields, but the executor still emits ~216 top-level keys (mostly null/empty)
inherited from the old multi-stage architecture.  This script rewrites each
raw file keeping only the whitelist fields, making the payload readable and
safe to use for future analysis.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "artifacts" / "benchmark_trajectory_gf_v1_v0_19_16" / "raw"

# Top-level fields emitted by the transparent repair loop that are worth keeping
TOP_KEEP = {
    # identity
    "task_id",
    "execution_source",
    "failure_type",
    "executor_status",
    # LLM / backend
    "planner_backend",
    "resolved_llm_provider",
    "backend_used",
    "uses_external_library",
    "live_request_count",
    # OMC outcome
    "check_model_pass",
    "simulate_pass",
    # behavioral oracle outcome
    "physics_contract_pass",
    "physics_contract_reasons",
    "contract_pass",
    "contract_fail_bucket",
    "scenario_results",
    # execution stats
    "rounds_used",
    "elapsed_sec",
    # error details
    "error_message",
    "compile_error",
    "simulate_error_message",
    "stderr_snippet",
    # per-round attempts
    "attempts",
    # transparent loop marker
    "transparent_repair_loop",
}

# Attempt-level fields to keep
ATTEMPT_KEEP = {
    "round",
    "transparent_repair_loop",
    "return_code",
    "check_model_pass",
    "simulate_pass",
    "observed_failure_type",
    "reason",
    "diagnostic_ir",
    "log_excerpt",
    "full_omc_error_output",
    "physics_contract_pass",
    "physics_contract_reasons",
    "contract_pass",
    "contract_fail_bucket",
    "scenario_results",
    "declaration_fix_repair",
    "patch_guard",
}


def _clean_attempt(a: dict) -> dict:
    return {k: v for k, v in a.items() if k in ATTEMPT_KEEP}


def _clean_payload(payload: dict) -> dict:
    cleaned = {k: v for k, v in payload.items() if k in TOP_KEEP}
    if "attempts" in cleaned and isinstance(cleaned["attempts"], list):
        cleaned["attempts"] = [_clean_attempt(a) for a in cleaned["attempts"]]
    return cleaned


def main() -> None:
    if not RAW_DIR.exists():
        print(f"raw dir not found: {RAW_DIR}")
        return

    files = sorted(RAW_DIR.glob("*.json"))
    print(f"Cleaning {len(files)} raw trajectory files in {RAW_DIR}")

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        original_keys = len(payload)
        cleaned = _clean_payload(payload)
        path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {path.name}: {original_keys} -> {len(cleaned)} top-level keys")

    print("\nDone.")


if __name__ == "__main__":
    main()
