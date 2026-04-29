#!/usr/bin/env python3
"""Run baseline on hard_boundary_v4 cases."""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_boundary_tool_use_baseline_v0_29_2 import (
    run_boundary_tool_use_baseline,
)

TASK_ROOT = REPO_ROOT / "assets_private" / "benchmarks" / "hard_boundary_v4" / "tasks" / "repair"
OUT_DIR = REPO_ROOT / "artifacts" / "hard_boundary_v4_baseline"

CASE_IDS = [
    "reinit_nonstate_01_missing_der",
    "flow_source_02_misdirected",
    "init_cascade_03_overdetermined",
]

for case_id in CASE_IDS:
    print(f"\n{'='*60}")
    print(f"Running baseline for: {case_id}")
    print(f"{'='*60}")
    result = run_boundary_tool_use_baseline(
        task_root=TASK_ROOT,
        out_dir=OUT_DIR / case_id,
        case_ids=[case_id],
        max_steps=10,
        max_token_budget=32000,
        planner_backend="auto",
        tool_profile="base",
    )
    print(f"Status: {result.get('status')}")
    print(f"Pass: {result.get('pass_count')}/{result.get('case_count')}")
    print(f"Behavioral fail: {result.get('behavioral_fail_count')}")
    print(f"Provider errors: {result.get('provider_error_count')}")
