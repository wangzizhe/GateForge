# GateForge

GateForge is a lightweight `run -> evidence -> gate` framework for simulation change governance.
It helps you answer: did this change pass checks, did it regress vs baseline, and why.

## What It Does

- Executes proposal-driven simulation checks (`mock`, `openmodelica`, `openmodelica_docker`)
- Emits machine-readable evidence (`.json`) and human-readable reports (`.md`)
- Compares candidate vs baseline and returns a gate decision (`PASS`, `FAIL`, `NEEDS_REVIEW`)
- Applies policy overlays for risk-aware decisions
- Supports repair/review/governance workflows for CI operations

## Quick Start

### Prerequisites

- Python `3.10+` (3.9 is not supported by this codebase)
- Docker Desktop running (for `openmodelica_docker` backend)

Optional but recommended for Docker backend:

```bash
docker pull openmodelica/openmodelica:v1.26.1-minimal
```

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run Tests

```bash
python3 -m unittest discover -s tests -v
```

### First End-to-End Demo (No Docker)

```bash
bash scripts/demo_proposal_flow.sh
cat artifacts/proposal_run_demo.json
```

## Core Workflow

### 1. Validate a Proposal

```bash
python3 -m gateforge.proposal_validate --in examples/proposals/proposal_v0.json
```

Optional structured validation output:

```bash
python3 -m gateforge.proposal_validate \
  --in examples/proposals/proposal_v0.json \
  --out artifacts/proposal_validate.json
```

### 2. Generate Candidate Evidence (Smoke)

```bash
python3 -m gateforge.smoke \
  --proposal examples/proposals/proposal_v0.json \
  --out artifacts/evidence_from_proposal.json
```

### 3. Run Full Proposal Pipeline (Check/Simulate/Regress)

```bash
python3 -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
```

Inspect results:

```bash
cat artifacts/proposal_run.json
cat artifacts/proposal_run.md
```

## Gate Decision Rules (v0)

A regression decision becomes `FAIL` when any of these are true:

- candidate `status != success`
- candidate `gate != PASS`
- baseline `check_ok=true` and candidate `check_ok=false`
- baseline `simulate_ok=true` and candidate `simulate_ok=false`
- runtime exceeds configured threshold
- strict comparison mode finds schema/backend/model script mismatch
- proposal-constrained regress compares incompatible baseline/candidate inputs

Policy layer (`policies/default_policy.json`) can downgrade some outcomes to `NEEDS_REVIEW`.

## Common Commands

### Smoke only

```bash
python3 -m gateforge.smoke --backend mock --out artifacts/evidence.json
```

### Regression only

```bash
python3 -m gateforge.regress \
  --candidate artifacts/candidate_from_proposal.json \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out artifacts/regression.json
```

### Batch benchmark pack

```bash
python3 -m gateforge.batch \
  --pack benchmarks/pack_v0.json \
  --out-dir artifacts/bench-pack \
  --summary-out artifacts/bench-pack/summary.json \
  --report-out artifacts/bench-pack/summary.md
```

### Auto baseline resolution

- Baseline index: `baselines/index.json`
- Use `--baseline auto` with `gateforge.run`

## Demos

For one-command examples and expected outputs, use:

- `DEMO.md`

Useful local demo scripts:

- `scripts/demo_all.sh`
- `scripts/demo_ci_matrix.sh`
- `scripts/demo_checker_config.sh`
- `scripts/demo_steady_state_checker.sh`
- `scripts/demo_behavior_metrics_checker.sh`
- `scripts/demo_repair_loop.sh`
- `scripts/demo_review_resolution.sh`
- `scripts/demo_governance_snapshot.sh`

Run demos under strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_all.sh
```

## Governance and Operations

Daily and release operations guidance lives in:

- `OPERATIONS.md`

Policy/config locations:

- default policy: `policies/default_policy.json`
- strict profile: `policies/profiles/industrial_strict_v0.json`
- promotion profiles: `policies/promotion/`
- repair strategy profiles: `policies/repair_strategy/`

## Repository Layout

- `gateforge/` core CLI modules
- `examples/` sample proposals, model scripts, and change sets
- `baselines/` reference baseline evidence and resolver index
- `policies/` policy overlays and profiles
- `schemas/` JSON schemas (proposal/planner)
- `scripts/` demo and helper scripts
- `tests/` unit tests
- `artifacts/` generated outputs (local runs)

## Troubleshooting

### Python version errors (for example, `type | None` errors)

You are likely on Python 3.9. Use Python `3.10+`.

### Docker backend fails

- Ensure Docker Desktop is running
- Pull image: `openmodelica/openmodelica:v1.26.1-minimal`
- Run backend check script:

```bash
bash scripts/check_docker_backend.sh
```

### Gate unexpectedly fails

Inspect these in order:

1. proposal run summary JSON/MD
2. regression JSON
3. candidate evidence JSON/MD
4. policy reasons and required human checks

## License

MIT (see `LICENSE`).
