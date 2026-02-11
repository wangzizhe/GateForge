# GateForge (minimal skeleton)

Minimal `run -> evidence -> gate` pipeline for learning and bootstrapping CI/regression governance.

## Goals

- Provide a reproducible evidence pipeline for simulation-related changes.
- Make gate decisions explainable via structured outputs (`json + md`).
- Keep backend execution replaceable (OpenModelica now, FMU runner later).

## Non-goals (current stage)

- Building a modeling copilot/agent.
- Supporting every simulation tool/backend.
- Building UI/dashboard or SaaS infrastructure.

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
cat artifacts/evidence.md
```

## Step 2: What this minimal CI does

- Runs tests on each push/PR.
- Uses a versioned baseline from `baselines/mock_baseline.json`.
- Generates `candidate` evidence (`.json + .md`).
- Runs a regression gate in strict mode (`artifacts/regression.json + artifacts/regression.md`).
- Uploads all evidence and regression artifacts in GitHub Actions.
- Provides an optional benchmark job (`workflow_dispatch` with `run_benchmark=true`) that does not block the main job.

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

Each run also writes a short markdown summary report (default: same path as `--out` with `.md`).
You can override it with:

```bash
python -m gateforge.smoke --backend openmodelica_docker --out artifacts/evidence-docker.json --report artifacts/run-report.md
```

GateForge runs OpenModelica in a temporary workspace and deletes it after execution, so compile/simulation artifacts do not pollute your project directory.

## Step 4: One-command local Docker backend check

```bash
bash scripts/check_docker_backend.sh
```

## Step 5: Regression gate (baseline vs candidate)

Compare repository baseline against current candidate:

```bash
python -m gateforge.smoke --backend mock --out artifacts/candidate.json
python -m gateforge.regress --baseline baselines/mock_baseline.json --candidate artifacts/candidate.json --out artifacts/regression.json
cat artifacts/regression.json
cat artifacts/regression.md
```

Behavior:
- `decision = PASS` -> command exits `0`
- `decision = FAIL` -> command exits `1` (can be used as CI gate)

Runtime regression threshold can be tuned (default `0.20` = +20%):

```bash
python -m gateforge.regress \
  --baseline baselines/mock_baseline.json \
  --candidate artifacts/candidate.json \
  --runtime-threshold 0.10 \
  --out artifacts/regression.json
```

In GitHub Actions, strict mode is enabled by default and runtime/script strictness is controlled by:

`GATEFORGE_RUNTIME_THRESHOLD` (see `.github/workflows/ci.yml`).
`GATEFORGE_STRICT_MODEL_SCRIPT` (default `false` in `.github/workflows/ci.yml`).

Strict mode is available for industrial-style comparability checks:

```bash
python -m gateforge.regress \
  --baseline baselines/mock_baseline.json \
  --candidate artifacts/candidate.json \
  --strict \
  --strict-model-script \
  --out artifacts/regression.json
```

Strict checks:
- `--strict`: fail if `schema_version` or `backend` mismatches
- `--strict-model-script`: additionally fail if `model_script` mismatches

## Step 6: Batch execution (multiple runs + summary)

Run a batch and generate per-run evidence plus an aggregate report:

```bash
python -m gateforge.batch --backend mock --out-dir artifacts/batch --summary-out artifacts/batch/summary.json --report-out artifacts/batch/summary.md
cat artifacts/batch/summary.json
cat artifacts/batch/summary.md
```

For OpenModelica Docker, pass multiple scripts:

```bash
python -m gateforge.batch \
  --backend openmodelica_docker \
  --script examples/openmodelica/minimal_probe.mos \
  --script examples/openmodelica/failures/simulate_error.mos \
  --out-dir artifacts/batch-om \
  --summary-out artifacts/batch-om/summary.json \
  --report-out artifacts/batch-om/summary.md
```

Or use a pack file (no repeated `--script` needed):

```bash
python -m gateforge.batch \
  --pack benchmarks/pack_v0.json \
  --out-dir artifacts/bench-pack \
  --summary-out artifacts/bench-pack/summary.json \
  --report-out artifacts/bench-pack/summary.md
```

Batch behavior:
- Default: stop on first failed run.
- Use `--continue-on-fail` to execute all runs even if some fail.

## Step 7: Benchmark Pack v0 (fixed cases + expected outcomes)

Run benchmark pack and validate expected outcomes:

```bash
python -m gateforge.benchmark \
  --pack benchmarks/pack_v0.json \
  --out-dir artifacts/benchmark_v0 \
  --summary-out artifacts/benchmark_v0/summary.json \
  --report-out artifacts/benchmark_v0/summary.md
```

Pack `benchmarks/pack_v0.json` currently defines 8 fixed cases with expected:
- 2 PASS cases
- 2 `script_parse_error` cases
- 2 `model_check_error` cases
- 2 `simulate_error` cases

Benchmark behavior:
- case matches expected -> PASS
- any mismatch -> FAIL (process exits `1`)

CI optional benchmark:
- Open GitHub Actions -> `ci` workflow -> `Run workflow`
- Set `run_benchmark=true`
- Benchmark job runs as non-blocking (`continue-on-error`) and uploads `benchmark-v0` artifacts.

## Step 8: Proposal schema v0 + validator

Validate a proposal before execution/gate:

```bash
python -m gateforge.proposal_validate --in examples/proposals/proposal_v0.json
```

Optional machine-readable validation result file:

```bash
python -m gateforge.proposal_validate \
  --in examples/proposals/proposal_v0.json \
  --out artifacts/proposal_validate.json
cat artifacts/proposal_validate.json
```

Current proposal schema file:

- `schemas/proposal.schema.json`

## Baseline governance

The baseline is versioned in-repo:

- `baselines/mock_baseline.json`
- `baselines/mock_baseline.md`

Update baseline only when expected behavior changes and is explicitly reviewed.
To refresh baseline files:

```bash
bash scripts/update_baseline.sh
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

After running failure fixtures, reset to default:

```bash
unset GATEFORGE_OM_SCRIPT
```

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
