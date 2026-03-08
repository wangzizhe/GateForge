# Agent Modelica 2-Hour Longhaul Plan v0

This plan is machine-readable and executable by:

`bash scripts/run_agent_modelica_longhaul_from_plan_v0.sh plans/agent_modelica_longhaul_120m_plan_v0.md`

## Goal

- Run the L4 uplift evidence chain continuously for about 2 hours.
- Keep segmented execution and resume support.
- Preserve mainline (`rule+strict`) and nightly-style (`gemini+observe`) evidence tracks inside each segment.

## Plan JSON

<!-- GATEFORGE_LONGHAUL_PLAN_V0_BEGIN -->
{
  "schema_version": "agent_modelica_longhaul_plan_v0",
  "plan_id": "l4_longhaul_120m_v0",
  "description": "Run L4 uplift evidence for around 120 minutes with segmented retries.",
  "longhaul": {
    "out_dir": "artifacts/agent_modelica_longhaul_v0_120m",
    "total_minutes": 120,
    "segment_timeout_sec": 1500,
    "max_segments": 5,
    "retry_per_segment": 1,
    "continue_on_fail": 1,
    "sleep_between_sec": 3,
    "resume": 1,
    "cwd": "."
  },
  "segment_command": "GATEFORGE_AGENT_L4_UPLIFT_OUT_DIR=\"$GATEFORGE_AGENT_LONGHAUL_SEGMENT_OUT_DIR\" bash scripts/run_agent_modelica_l4_uplift_evidence_v0.sh",
  "env": {
    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND": "rule",
    "GATEFORGE_AGENT_L4_UPLIFT_MAIN_GATE_MODE": "strict",
    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND": "gemini",
    "GATEFORGE_AGENT_L4_UPLIFT_NIGHT_GATE_MODE": "observe",
    "GATEFORGE_AGENT_L4_UPLIFT_MIN_DELTA_SUCCESS_PP": "5",
    "GATEFORGE_AGENT_L4_UPLIFT_MAX_REGRESSION_WORSEN_PP": "2",
    "GATEFORGE_AGENT_L4_UPLIFT_MAX_PHYSICS_WORSEN_PP": "2"
  }
}
<!-- GATEFORGE_LONGHAUL_PLAN_V0_END -->

## Expected Artifacts

- `artifacts/agent_modelica_longhaul_v0_120m/summary.json`
- `artifacts/agent_modelica_longhaul_v0_120m/state.json`
- `artifacts/agent_modelica_longhaul_v0_120m/segments.jsonl`
- `artifacts/agent_modelica_longhaul_v0_120m/runs/segment_*/summary.json`
