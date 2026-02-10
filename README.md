# GateForge (minimal skeleton)

Minimal `run -> evidence -> gate` pipeline for learning and bootstrapping CI/regression governance.

## Prerequisites

- Python 3.10+
- Docker Desktop installed and running
- OpenModelica Docker image:

```bash
docker pull openmodelica/openmodelica:v1.26.1-minimal
```

## Step 1: Install and run locally (mock backend)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
python -m gateforge.smoke --backend mock --out artifacts/evidence.json
cat artifacts/evidence.json
```

## Step 2: What this minimal CI does

- Runs tests on each push/PR.
- Runs a smoke pipeline that produces `artifacts/evidence.json`.
- Uploads the evidence artifact in GitHub Actions.

This is intentionally small. It proves your governance layer can always produce machine-readable evidence before adding real simulation complexity.

## Step 3: OpenModelica via Docker (recommended on macOS)

```bash
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/evidence-docker.json
cat artifacts/evidence-docker.json
```

This backend now runs a real `.mos` script:

`examples/openmodelica/minimal_probe.mos`

The script loads:

`examples/openmodelica/MinimalProbe.mo`

By default this uses:

`openmodelica/openmodelica:v1.26.1-minimal`

You can override the image tag without changing code:

```bash
export GATEFORGE_OM_IMAGE=openmodelica/openmodelica:v1.26.1-minimal
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/evidence-docker.json
```

You can also override which `.mos` script to run:

```bash
export GATEFORGE_OM_SCRIPT=examples/openmodelica/minimal_probe.mos
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/evidence-docker.json
```

Expected success signals:
- `"status": "success"`
- `"gate": "PASS"`
- `"check_ok": true`
- `"simulate_ok": true`

The generated evidence includes:
- `failure_type`: classified failure reason (`none`, `script_parse_error`, `model_check_error`, `simulate_error`, `docker_error`, ...)
- `model_script`: script executed by `omc`
- `exit_code`: process exit code from the backend run
- `check_ok`: whether model checking succeeded
- `simulate_ok`: whether simulation succeeded

GateForge runs OpenModelica in a temporary workspace and deletes it after execution, so compile/simulation artifacts do not pollute your project directory.

## Step 4: One-command local Docker backend check

```bash
bash scripts/check_docker_backend.sh
```

## Failure fixtures (taxonomy v0)

Run these to validate failure classification:

```bash
export GATEFORGE_OM_SCRIPT=examples/openmodelica/failures/script_parse_error.mos
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/failure_script_parse.json

export GATEFORGE_OM_SCRIPT=examples/openmodelica/failures/model_check_error.mos
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/failure_model_check.json

export GATEFORGE_OM_SCRIPT=examples/openmodelica/failures/simulate_error.mos
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/failure_simulate.json
```

Expected `failure_type` values:
- `script_parse_error`
- `model_check_error`
- `simulate_error`

## Repository layout

- `gateforge/`: core pipeline and CLI entrypoint
- `examples/openmodelica/`: `.mo` model and `.mos` script fixtures
- `schemas/`: evidence schema
- `tests/`: smoke/regression tests
- `scripts/`: local helper scripts

## Troubleshooting

- `permission denied ... docker.sock`:
  Docker Desktop is not running or current shell cannot access Docker daemon.
- `Error: No viable alternative near token: model`:
  `.mos` is a script file; keep class definitions in `.mo` and load them from `.mos`.
