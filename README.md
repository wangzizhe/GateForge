# GateForge

Governance layer for AI/Agent-authored Modelica simulation changes.

GateForge turns a change into an engineering decision flow that is:
- verifiable
- reproducible
- auditable
- policy-driven

## What It Is

GateForge is not a modeling copilot. It is a gate around model changes:

`proposal -> run -> evidence -> regress -> policy -> review`

Current first backend: `openmodelica_docker`.

## What It Is Not (Current Scope)

- Not a full agent platform
- Not a full UI/SaaS product
- Not all simulation tools/backends yet

## Quickstart (5 Minutes)

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Run tests

```bash
python -m unittest discover -s tests -v
```

### 3. Run minimal proposal flow

```bash
python -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
cat artifacts/proposal_run.json
```

## Core Commands

### Smoke / Evidence

```bash
python -m gateforge.smoke --backend mock --out artifacts/evidence.json
```

### Regression Gate

```bash
python -m gateforge.regress \
  --baseline baselines/mock_baseline.json \
  --candidate artifacts/candidate.json \
  --out artifacts/regression.json
```

### Proposal Validate

```bash
python -m gateforge.proposal_validate --in examples/proposals/proposal_v0.json
```

## Medium Governance Chain (Current Mainline)

### 1) Medium benchmark truth set

```bash
bash scripts/demo_medium_pack_v1.sh
```

### 2) Mismatch analysis

```bash
bash scripts/demo_medium_pack_v1_analysis.sh
```

### 3) History / trend / advisor / dashboard

```bash
bash scripts/demo_medium_pack_v1_dashboard.sh
```

Main artifacts are under:
- `artifacts/benchmark_medium_v1/summary.json`
- `artifacts/benchmark_medium_v1/analysis.json`
- `artifacts/benchmark_medium_v1/history_summary.json`
- `artifacts/benchmark_medium_v1/history_trend.json`
- `artifacts/benchmark_medium_v1/advisor.json`
- `artifacts/benchmark_medium_v1/dashboard.json`

## Policy Patch Governance Chain

```bash
bash scripts/demo_governance_policy_patch_dashboard.sh
```

Main artifacts are under:
- `artifacts/governance_policy_patch_apply_demo/`
- `artifacts/governance_policy_patch_history_demo/`
- `artifacts/governance_policy_patch_dashboard_demo/`

## MVP Freeze (Release Readiness)

```bash
bash scripts/mvp_freeze_check.sh
```

Outputs:
- `artifacts/mvp_freeze/summary.json`
- `artifacts/mvp_freeze/summary.md`

Verdict values:
- `MVP_FREEZE_PASS`
- `MVP_FREEZE_FAIL` (with `blocking_step`)

## CI (Optional Manual Jobs)

Workflow: `ci` (`workflow_dispatch`)

Set `run_benchmark=true` to run non-blocking optional chains:
- benchmark optional
- medium governance optional
- mvp freeze optional

Artifacts include:
- `benchmark-v0`
- `medium-governance-v1`
- `mvp-freeze-v1`

## Repository Map

- `gateforge/` core commands and logic
- `benchmarks/` benchmark packs
- `examples/` Modelica scripts, fixtures, proposals
- `policies/` governance policy configs
- `schemas/` JSON schemas
- `scripts/` one-command demo and ops scripts
- `tests/` unit/integration tests

## More Documentation

- Detailed demo cookbook: `DEMO.md`
- Previous full README (archived): `docs/legacy-readme.md`
