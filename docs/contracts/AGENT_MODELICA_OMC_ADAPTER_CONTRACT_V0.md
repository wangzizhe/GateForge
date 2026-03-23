# Agent Modelica OMC Adapter Contract v0

## Scope
- Domain: `electrical` only.
- Backends: `openmodelica_docker` (default), `omc` (optional local).
- Stage: L2 compile contract (`loadModel/loadFile/checkModel`), no L4 policy semantics.

## Required Behavior
1. Docker backend must run with:
- `installPackage(Modelica);`
- `loadModel(Modelica);`
- absolute host mount path for workspace
- absolute host mount path for OMC library cache (`/root/.openmodelica/libraries`)

2. Compile gate script sequence:
- `loadFile(<model.mo>);`
- `checkModel(<ModelName>);`
- `getErrorString();`

3. Output contract (JSON) must include:
- `check_model_pass`
- `simulate_pass` (for live executor compatibility, can be false in compile-only gate)
- `error_message`
- `compile_error`
- `stderr_snippet`
- `backend_used`
- `elapsed_sec`

4. Infra failure classifier must detect:
- timeout
- docker permission denied
- docker volume mount invalid
- MSL load failure
- path not found

## Minimal Smoke Command
```bash
GATEFORGE_AGENT_L2_DUAL_GATE_SCALES=small \
GATEFORGE_AGENT_L2_DUAL_GATE_MAX_TASKS=2 \
bash scripts/run_agent_modelica_l2_dual_gate_v0.sh
```

## Timeout Profile (default)
- `small`: 180s
- `medium`: 240s
- `large`: 420s

Timeouts can be overridden by environment variables in calling scripts.
