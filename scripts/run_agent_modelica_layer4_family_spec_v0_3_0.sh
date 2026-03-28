#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_LAYER4_FAMILY_SPEC_V030_OUT_DIR:-artifacts/agent_modelica_layer4_family_spec_v0_3_0}"
SPEC_PATH="$OUT_DIR/spec.json"
OUT_PATH="$OUT_DIR/summary.json"
REPORT_OUT="$OUT_DIR/summary.md"

mkdir -p "$OUT_DIR"

python3 - "$SPEC_PATH" <<'PY'
import json
import sys
from pathlib import Path

spec_path = Path(sys.argv[1])
payload = {
    "schema_version": "agent_modelica_layer4_family_spec_v1",
    "version_id": "v0.3.0",
    "generated_for": "block_1_layer4_family_spec",
    "families": [
        {
            "family_id": "initialization_singularity",
            "display_name": "Initialization Singularity",
            "enabled_for_v0_3_0": True,
            "viability_status": "approved_v0_3_0",
            "expected_layer_hint": "layer_4",
            "mutation_acceptance_constraints": [
                "source model must remain source-viable before mutation",
                "mutation must preserve deterministic reproduction",
                "failure should arise from initialization singularity rather than syntax or path breakage",
            ],
            "validation_criterion": {
                "min_observed_layer4_share_pct": 60.0,
                "max_gateforge_success_rate_pct": 85.0,
            },
            "notes": [
                "prefer controlled initialization conflicts or overconstrained initialization regimes",
            ],
        },
        {
            "family_id": "structural_singularity",
            "display_name": "Structural Singularity",
            "enabled_for_v0_3_0": False,
            "viability_status": "deferred_v0_3_1",
            "expected_layer_hint": "layer_4",
            "mutation_acceptance_constraints": [
                "source model must remain source-viable before mutation",
                "mutation must preserve deterministic reproduction",
                "spec review must prove algebraic-structure change does not collapse source viability screening",
            ],
            "validation_criterion": {
                "min_observed_layer4_share_pct": 60.0,
                "min_stage4_stage5_share_pct": 40.0,
            },
            "notes": [
                "deferred because algebraic-structure mutations are materially riskier than parameter or initialization perturbations",
            ],
        },
        {
            "family_id": "runtime_numerical_instability",
            "display_name": "Runtime Numerical Instability",
            "enabled_for_v0_3_0": True,
            "viability_status": "approved_v0_3_0",
            "expected_layer_hint": "layer_4",
            "mutation_acceptance_constraints": [
                "source model must remain source-viable before mutation",
                "mutation must preserve deterministic reproduction",
                "instability should emerge during simulate/runtime rather than compile stage",
            ],
            "validation_criterion": {
                "min_observed_layer4_share_pct": 60.0,
                "min_stage4_stage5_share_pct": 50.0,
            },
            "notes": [
                "prefer parameter regimes that induce solver sensitivity, stiffness, or unstable runtime dynamics",
            ],
        },
        {
            "family_id": "hard_multiround_simulate_failure",
            "display_name": "Hard Multi-Round Simulate Failure",
            "enabled_for_v0_3_0": True,
            "viability_status": "approved_v0_3_0",
            "expected_layer_hint": "layer_4",
            "mutation_acceptance_constraints": [
                "source model must remain source-viable before mutation",
                "mutation must preserve deterministic reproduction",
                "single-round repair should usually fail or underperform relative to harder multiround behavior",
            ],
            "validation_criterion": {
                "min_observed_layer4_share_pct": 60.0,
                "min_hard_case_rate_pct": 40.0,
            },
            "notes": [
                "use failure families that tend to require budgeted search or stage-aware replanning",
            ],
        },
    ],
}
spec_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

GATEFORGE_AGENT_LAYER4_FAMILY_SPEC="$SPEC_PATH" \
GATEFORGE_AGENT_LAYER4_FAMILY_SPEC_OUT="$OUT_PATH" \
GATEFORGE_AGENT_LAYER4_FAMILY_SPEC_REPORT_OUT="$REPORT_OUT" \
bash scripts/run_agent_modelica_layer4_family_spec_v1.sh
