#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/mvp_freeze"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/summary.json "$OUT_DIR"/summary.md "$OUT_DIR"/tests.log "$OUT_DIR"/medium_dashboard.log "$OUT_DIR"/mutation_dashboard.log "$OUT_DIR"/policy_autotune.log "$OUT_DIR"/policy_dashboard.log "$OUT_DIR"/ci_matrix.log

set +e
python3 -m unittest discover -s tests -v >"$OUT_DIR/tests.log" 2>&1
TESTS_RC=$?

bash scripts/demo_medium_pack_v1_dashboard.sh >"$OUT_DIR/medium_dashboard.log" 2>&1
MEDIUM_RC=$?

bash scripts/demo_mutation_dashboard.sh >"$OUT_DIR/mutation_dashboard.log" 2>&1
MUTATION_RC=$?

bash scripts/demo_policy_autotune_history.sh >"$OUT_DIR/policy_autotune.log" 2>&1
POLICY_AUTOTUNE_RC=$?

bash scripts/demo_governance_policy_patch_dashboard.sh >"$OUT_DIR/policy_dashboard.log" 2>&1
POLICY_RC=$?

bash scripts/demo_ci_matrix.sh --none --checker-demo --autopilot-dry-run --governance-policy-patch-dashboard-demo >"$OUT_DIR/ci_matrix.log" 2>&1
MATRIX_RC=$?
set -e

python3 -m gateforge.mvp_freeze \
  --tests-rc "$TESTS_RC" \
  --medium-dashboard-rc "$MEDIUM_RC" \
  --mutation-dashboard-rc "$MUTATION_RC" \
  --policy-autotune-rc "$POLICY_AUTOTUNE_RC" \
  --policy-dashboard-rc "$POLICY_RC" \
  --ci-matrix-rc "$MATRIX_RC" \
  --medium-dashboard-json artifacts/benchmark_medium_v1/dashboard.json \
  --mutation-dashboard-json artifacts/mutation_dashboard_demo/summary.json \
  --policy-autotune-json artifacts/policy_autotune_history_demo/demo_summary.json \
  --policy-dashboard-json artifacts/governance_policy_patch_dashboard_demo/demo_summary.json \
  --ci-matrix-json artifacts/ci_matrix_summary.json \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
