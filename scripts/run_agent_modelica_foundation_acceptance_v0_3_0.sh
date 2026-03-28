#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_V030_OUT_DIR:-artifacts/agent_modelica_foundation_acceptance_v0/v0_3_0}"
OUT_PATH="$OUT_DIR/summary.json"
REPORT_OUT="$OUT_DIR/summary.md"
SPEC_PATH="$OUT_DIR/spec.json"

mkdir -p "$OUT_DIR"

python3 - "$SPEC_PATH" <<'PY'
import json
import sys
from pathlib import Path

spec_path = Path(sys.argv[1])
payload = {
    "layer_summary": "artifacts/agent_modelica_difficulty_layer_v0_2_6/summary.json",
    "required_regeneration_paths": [
        "artifacts/agent_modelica_difficulty_layer_v0_2_6/summary.json",
        "artifacts/agent_modelica_planner_sensitive_taskset_builder_v1/summary.json",
        "artifacts/agent_modelica_planner_sensitive_taskset_builder_v1/taskset_frozen.json",
        "artifacts/agent_modelica_planner_sensitive_pack_builder_v1/gf_results_track_a_v0_2_5.json",
    ],
    "lanes": [
        {
            "lane_id": "track_a",
            "label": "Track A v0.2.5 rich results",
            "run_results": "artifacts/agent_modelica_planner_sensitive_pack_builder_v1/gf_results_track_a_v0_2_5.json",
            "sidecar": "artifacts/agent_modelica_difficulty_layer_v0_2_6/track_a/layer_metadata.json",
            "planner_expected": False,
            "require_stage_subtype_coverage": True,
        },
        {
            "lane_id": "planner_sensitive",
            "label": "Planner-sensitive eval baseline",
            "run_results": "artifacts/agent_modelica_planner_sensitive_eval_v1/results_baseline.json",
            "sidecar": "artifacts/agent_modelica_difficulty_layer_v0_2_6/planner_sensitive/layer_metadata.json",
            "planner_expected": True,
            "require_stage_subtype_coverage": False,
        },
    ],
    "thresholds": {
        "min_stage_subtype_coverage_pct": 95.0,
        "max_unresolved_success_count": 0,
        "min_planner_invoked_rate_pct_when_expected": 50.0,
        "max_layer4_share_pct": 40.0,
    },
}
spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_SPEC="$SPEC_PATH" \
GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_OUT="$OUT_PATH" \
GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_REPORT_OUT="$REPORT_OUT" \
bash scripts/run_agent_modelica_foundation_acceptance_v0.sh
