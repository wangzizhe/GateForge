from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_workspace_style_probe_v0_67_0 import (
    DEFAULT_OUT_DIR,
    DEFAULT_TASKS,
    _extract_omc_diagnostics,
    _extract_model_name,
    _run_omc_check,
    run_workspace_style_case,
    run_workspace_style_probe,
)


def run_two_phase_case(
    case: dict[str, Any],
    *,
    out_dir: Path,
    max_steps: int = 10,
    max_token_budget: int = 32000,
    planner_backend: str = "auto",
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    current_text = str(case["model_text"])
    case_workspace = (out_dir / "workspaces" / case_id).resolve()
    case_workspace.mkdir(parents=True, exist_ok=True)
    (case_workspace / "initial.mo").write_text(current_text, encoding="utf-8")

    # Phase 1: harness runs OMC check on initial model
    initial_path = case_workspace / "initial.mo"
    output, _ = _run_omc_check(workspace=case_workspace, candidate_path=initial_path)
    diags = _extract_omc_diagnostics(str(output or ""))

    diagnostics_text = "--- PRE-COMPUTED DIAGNOSTICS ---\n"
    diagnostics_text += json.dumps(diags, indent=2, sort_keys=True)

    model_name_extracted = _extract_model_name(current_text)
    case["model_name"] = model_name_extracted
    case["model_text"] = current_text

    # Phase 2: LLM gets clean context with diagnostics
    return run_workspace_style_case(
        case,
        out_dir=out_dir,
        max_steps=max_steps,
        max_token_budget=max_token_budget,
        planner_backend=planner_backend,
        preload_diagnostics=diagnostics_text,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Two-phase Modelica repair: harness diagnostics → LLM fix"
    )
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--max-token-budget", type=int, default=64000)
    parser.add_argument("--planner-backend", default="auto")
    parser.add_argument("--per-case-timeout-sec", type=int, default=240)
    parser.add_argument("--summary-version", default="v0.68.0")
    args = parser.parse_args()

    summary = run_workspace_style_probe(
        tasks_path=args.tasks,
        out_dir=args.out_dir,
        case_ids=list(args.case_id or []),
        limit=args.limit,
        max_steps=args.max_steps,
        max_token_budget=args.max_token_budget,
        planner_backend=args.planner_backend,
        per_case_timeout_sec=args.per_case_timeout_sec,
        summary_version=args.summary_version,
        run_case_fn=run_two_phase_case,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
