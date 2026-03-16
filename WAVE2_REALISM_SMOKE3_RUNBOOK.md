# Wave2 Realism Smoke3 Runbook

This runbook defines the minimum live smoke for `wave2 realism v1`.

## Goal

Validate the real `Gemini + Docker + OMC` path on one representative task per new error family before launching the full `baseline_off_live` run.

The smoke taskset is fixed to these three tasks:

- `wave2_buildings_loads_overconstrained_system`
- `wave2_ibpsa_loads_parameter_binding_error`
- `wave2_transform_simplebattery_test_array_dimension_mismatch`

## Build Smoke3 Taskset

```bash
python3 - <<'PY'
import json
from pathlib import Path

src = Path("artifacts/agent_modelica_wave2_realism_taskset_v1_devcheck/taskset_frozen.json")
dst = Path("artifacts/agent_modelica_wave2_smoke3/taskset_frozen.json")
payload = json.loads(src.read_text(encoding="utf-8"))
wanted = {
    "wave2_buildings_loads_overconstrained_system",
    "wave2_ibpsa_loads_parameter_binding_error",
    "wave2_transform_simplebattery_test_array_dimension_mismatch",
}
subset = [row for row in payload.get("tasks", []) if row.get("task_id") in wanted]
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps({"tasks": subset}, indent=2), encoding="utf-8")
print(dst)
PY
```

## Run Baseline Smoke

```bash
export GATEFORGE_AGENT_LIVE_PLANNER_BACKEND=gemini
export GATEFORGE_AGENT_LIVE_OM_BACKEND=openmodelica_docker
export GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE=openmodelica/openmodelica:v1.26.1-minimal
export GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC=120

LIVE_EXECUTOR_CMD='python3 -m gateforge.agent_modelica_live_executor_gemini_v1 --task-id "__TASK_ID__" --failure-type "__FAILURE_TYPE__" --expected-stage "__EXPECTED_STAGE__" --source-model-path "__SOURCE_MODEL_PATH__" --mutated-model-path "__MUTATED_MODEL_PATH__" --source-library-path "__SOURCE_LIBRARY_PATH__" --source-package-name "__SOURCE_PACKAGE_NAME__" --source-library-model-path "__SOURCE_LIBRARY_MODEL_PATH__" --source-qualified-model-name "__SOURCE_QUALIFIED_MODEL_NAME__" --repair-actions __REPAIR_ACTIONS_SHQ__ --max-rounds "__MAX_ROUNDS__" --timeout-sec "__MAX_TIME_SEC__" --planner-backend "'"${GATEFORGE_AGENT_LIVE_PLANNER_BACKEND}"'" --backend "'"${GATEFORGE_AGENT_LIVE_OM_BACKEND}"'" --docker-image "'"${GATEFORGE_AGENT_LIVE_OM_DOCKER_IMAGE}"'"'

python3 -m gateforge.agent_modelica_run_contract_v1 \
  --taskset artifacts/agent_modelica_wave2_smoke3/taskset_frozen.json \
  --mode live \
  --max-rounds 2 \
  --max-time-sec 300 \
  --runtime-threshold 0.2 \
  --live-executor-cmd "$LIVE_EXECUTOR_CMD" \
  --live-timeout-sec 300 \
  --live-max-output-chars 2400 \
  --results-out artifacts/agent_modelica_wave2_smoke3/results.json \
  --out artifacts/agent_modelica_wave2_smoke3/summary.json
```

## Read Results

Primary files:

- `artifacts/agent_modelica_wave2_smoke3/summary.json`
- `artifacts/agent_modelica_wave2_smoke3/results.json`

Minimum acceptance:

- `records` count is `3`
- every record has `task_id`, `passed`, `error_message`, `attempts`
- no task hangs without a result row
- failure, if any, must be diagnosable rather than silent timeout
