#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

cmd="${1:-}"

usage() {
  cat <<'TXT'
GateForge current lane runner (v1)

Usage:
  bash scripts/run_agent_modelica_now_v1.sh <command>

Commands:
  compat-smoke
    Run environment compatibility probes (Docker, image, MSL, compile, simulate).
    Exits non-zero on first infrastructure failure.

  calib
    Run strict OMC calibration pack for mutation quality.

  loop-mini-live
    Run a lightweight live learning loop (Docker OMC + rule planner).

  preflight
    Run release preflight with mandatory live smoke.
    Automatically runs compat-smoke first; aborts if environment is broken.
TXT
}

if [ -z "$cmd" ] || [ "$cmd" = "help" ] || [ "$cmd" = "--help" ] || [ "$cmd" = "-h" ]; then
  usage
  exit 0
fi

if [ "$cmd" = "compat-smoke" ]; then
  docker_image="${GATEFORGE_DOCKER_IMAGE:-openmodelica/openmodelica:v1.26.1-minimal}"
  whitelist="${GATEFORGE_COMPAT_WHITELIST:-data/modelica_compatibility_whitelist_v1.json}"
  out_dir="${GATEFORGE_COMPAT_SMOKE_OUT_DIR:-artifacts/compatibility_smoke}"
  timeout="${GATEFORGE_COMPAT_SMOKE_TIMEOUT_SEC:-180}"
  python3 -m gateforge.agent_modelica_compatibility_detector_v1 \
    --docker-image "$docker_image" \
    --whitelist "$whitelist" \
    --out "$out_dir/compatibility_report.json" \
    --md-out "$out_dir/compatibility_report.md" \
    --timeout-sec "$timeout"
  exit $?
fi

if [ "$cmd" = "calib" ]; then
  out_dir="${GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR:-artifacts/agent_modelica_problem_plan_execution_v1_now}"
  GATEFORGE_AGENT_PROBLEM_PLAN_EXEC_OUT_DIR="$out_dir" \
    bash scripts/run_agent_modelica_problem_plan_execution_v1.sh
  exit 0
fi

if [ "$cmd" = "loop-mini-live" ]; then
  out_dir="${GATEFORGE_AGENT_MVP_MUTANT_REPAIR_LOOP_OUT_DIR:-artifacts/agent_modelica_mvp_mutant_repair_learning_loop_v1_now}"
  live_cmd="${GATEFORGE_AGENT_LIVE_EXECUTOR_CMD:-python3 -m gateforge.agent_modelica_live_executor_v1 --task-id \"__TASK_ID__\" --failure-type \"__FAILURE_TYPE__\" --expected-stage \"__EXPECTED_STAGE__\" --source-model-path \"__SOURCE_MODEL_PATH__\" --mutated-model-path \"__MUTATED_MODEL_PATH__\" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds \"__MAX_ROUNDS__\" --timeout-sec \"__MAX_TIME_SEC__\" --planner-backend \"rule\" --backend \"openmodelica_docker\" --docker-image \"openmodelica/openmodelica:v1.26.1-minimal\"}"
  GATEFORGE_AGENT_MVP_MUTANT_REPAIR_LOOP_OUT_DIR="$out_dir" \
    GATEFORGE_AGENT_RUN_MODE="${GATEFORGE_AGENT_RUN_MODE:-live}" \
    GATEFORGE_AGENT_USE_HARDPACK="${GATEFORGE_AGENT_USE_HARDPACK:-0}" \
    GATEFORGE_AGENT_PER_SCALE_TOTAL="${GATEFORGE_AGENT_PER_SCALE_TOTAL:-1}" \
    GATEFORGE_AGENT_PER_SCALE_FAILURE_TARGETS="${GATEFORGE_AGENT_PER_SCALE_FAILURE_TARGETS:-1,0,0}" \
    GATEFORGE_AGENT_MAX_ROUNDS="${GATEFORGE_AGENT_MAX_ROUNDS:-2}" \
    GATEFORGE_AGENT_MAX_TIME_SEC="${GATEFORGE_AGENT_MAX_TIME_SEC:-120}" \
    GATEFORGE_AGENT_LIVE_TIMEOUT_SEC="${GATEFORGE_AGENT_LIVE_TIMEOUT_SEC:-90}" \
    GATEFORGE_AGENT_ALLOW_BASELINE_FAIL="${GATEFORGE_AGENT_ALLOW_BASELINE_FAIL:-1}" \
    GATEFORGE_AGENT_LIVE_EXECUTOR_CMD="$live_cmd" \
    bash scripts/run_agent_modelica_mvp_mutant_repair_learning_loop_v1.sh
  exit 0
fi

if [ "$cmd" = "preflight" ]; then
  # Fail-fast: run compatibility smoke before expensive preflight work.
  if [ "${GATEFORGE_SKIP_COMPAT_SMOKE:-0}" != "1" ]; then
    echo "=== Compatibility smoke (fail-fast gate) ==="
    if ! bash "$0" compat-smoke; then
      echo "PREFLIGHT ABORTED: environment compatibility smoke failed." >&2
      echo "Fix the infrastructure issues above, or set GATEFORGE_SKIP_COMPAT_SMOKE=1 to bypass." >&2
      exit 1
    fi
    echo "=== Compatibility smoke passed ==="
  fi
  GATEFORGE_AGENT_RELEASE_RUN_LIVE_SMOKE="${GATEFORGE_AGENT_RELEASE_RUN_LIVE_SMOKE:-1}" \
    bash scripts/run_agent_modelica_release_preflight_v0_1_5.sh
  exit 0
fi

echo "unknown command: $cmd" >&2
usage >&2
exit 2
