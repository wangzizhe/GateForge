# GateForge

<p align="center">
  <a href="https://github.com/wangzizhe/GateForge/actions/workflows/ci.yml" style="text-decoration:none;"><img src="https://github.com/wangzizhe/GateForge/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>&nbsp;
  <a href="https://github.com/wangzizhe/GateForge/releases" style="text-decoration:none;"><img src="https://img.shields.io/github/release/wangzizhe/GateForge.svg?include_prereleases" alt="Release" /></a>&nbsp;
  <a href="LICENSE" style="text-decoration:none;"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>&nbsp;
  <a href="https://www.python.org/" style="text-decoration:none;"><img src="https://img.shields.io/badge/python-%3E%3D3.10-3776AB.svg" alt="Python >= 3.10" /></a>
</p>

<p align="center" style="margin: 0.75rem auto 1rem; max-width: 920px; padding: 0.75rem 1rem; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa;">
  <strong>GateForge determines whether AI- or simulation-driven changes can be safely deployed to production for Physical AI systems.</strong>
</p>

GateForge turns a change into an engineering decision flow that is:
- verifiable
- reproducible
- auditable
- policy-driven

## What It Is

GateForge is not a modeling copilot. It is a gate around model changes:

`proposal -> run -> evidence -> regress -> policy -> review`

Current scope: Modelica workflows as the first Physical AI pressure-test domain.

Current first backend: `openmodelica_docker`.

## What It Is Not (Current Scope)

- Not a full agent platform
- Not a full UI/SaaS product
- Not all simulation tools/backends yet
- Not tied to a single simulator long-term (OpenModelica is the current backend)

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

## Mutation Data Flywheel (v0)

Generate synthetic mutation cases, compile a benchmark pack, and run it end-to-end:

```bash
bash scripts/demo_mutation_pack_v0.sh
```

Use a fast local mode (for tests/dev loop):

```bash
MUTATION_BACKEND=mock MUTATION_COUNT=8 bash scripts/demo_mutation_pack_v0.sh
```

Main artifacts are under:
- `artifacts/mutation_pack_v0/manifest.json`
- `artifacts/mutation_pack_v0/pack.json`
- `artifacts/mutation_pack_v0/summary.json`
- `artifacts/mutation_pack_v0/demo_summary.json`

### v1 (metrics-enabled mutation pack)

```bash
bash scripts/demo_mutation_pack_v1.sh
```

Fast mode:

```bash
MUTATION_BACKEND=mock MUTATION_COUNT=24 bash scripts/demo_mutation_pack_v1.sh
```

Main artifacts are under:
- `artifacts/mutation_pack_v1/manifest.json`
- `artifacts/mutation_pack_v1/pack.json`
- `artifacts/mutation_pack_v1/summary.json`
- `artifacts/mutation_pack_v1/metrics.json`
- `artifacts/mutation_pack_v1/demo_summary.json`

Compare mutation pack quality between versions:

```bash
bash scripts/demo_mutation_pack_compare.sh
```

Output:
- `artifacts/mutation_pack_compare_demo/summary.json`
- `artifacts/mutation_pack_compare_demo/summary.md`

Mutation governance dashboard (metrics + history + trend + compare):

```bash
bash scripts/demo_mutation_dashboard.sh
```

Output:
- `artifacts/mutation_dashboard_demo/summary.json`
- `artifacts/mutation_dashboard_demo/summary.md`

Mutation-driven policy patch flow (advisor -> proposal -> apply):

```bash
bash scripts/demo_mutation_policy_patch.sh
```

Output:
- `artifacts/mutation_policy_patch_demo/advisor.json`
- `artifacts/mutation_policy_patch_demo/proposal.json`
- `artifacts/mutation_policy_patch_demo/apply.json`
- `artifacts/mutation_policy_patch_demo/summary.json`

Cross-layer policy auto-tuning (governance + mutation + medium benchmark):

```bash
bash scripts/demo_policy_autotune.sh
```

Output:
- `artifacts/policy_autotune_demo/advisor.json`
- `artifacts/policy_autotune_demo/proposal.json`
- `artifacts/policy_autotune_demo/apply.json`
- `artifacts/policy_autotune_demo/summary.json`

Policy auto-tuning history/trend:

```bash
bash scripts/demo_policy_autotune_history.sh
```

Output:
- `artifacts/policy_autotune_history_demo/summary.json`
- `artifacts/policy_autotune_history_demo/trend.json`
- `artifacts/policy_autotune_history_demo/demo_summary.json`

Policy auto-tuning governance flow (advisor-driven promote compare/apply + effectiveness):

```bash
bash scripts/demo_policy_autotune_governance.sh
```

Output:
- `artifacts/policy_autotune_governance_demo/flow_summary.json`
- `artifacts/policy_autotune_governance_demo/effectiveness.json`
- `artifacts/policy_autotune_governance_demo/summary.json`

Policy auto-tuning governance history dashboard:

```bash
bash scripts/demo_policy_autotune_governance_dashboard.sh
```

Output:
- `artifacts/policy_autotune_governance_history_demo/summary.json`
- `artifacts/policy_autotune_governance_history_demo/trend.json`
- `artifacts/policy_autotune_governance_history_demo/dashboard.json`
- `artifacts/policy_autotune_governance_history_demo/demo_summary.json`

Policy auto-tuning governance advisor (dashboard -> action -> patch apply):

```bash
bash scripts/demo_policy_autotune_governance_advisor.sh
```

Output:
- `artifacts/policy_autotune_governance_advisor_demo/advisor.json`
- `artifacts/policy_autotune_governance_advisor_demo/proposal.json`
- `artifacts/policy_autotune_governance_advisor_demo/apply.json`
- `artifacts/policy_autotune_governance_advisor_demo/summary.json`

Policy auto-tuning governance advisor history (advisor records -> history -> trend):

```bash
bash scripts/demo_policy_autotune_governance_advisor_history.sh
```

Output:
- `artifacts/policy_autotune_governance_advisor_history_demo/history.jsonl`
- `artifacts/policy_autotune_governance_advisor_history_demo/summary.json`
- `artifacts/policy_autotune_governance_advisor_history_demo/trend.json`
- `artifacts/policy_autotune_governance_advisor_history_demo/demo_summary.json`

Governance snapshot (with advisor history signal):

```bash
bash scripts/demo_governance_snapshot_with_advisor_history.sh
```

Output:
- `artifacts/governance_snapshot_advisor_history_demo/summary.json`
- `artifacts/governance_snapshot_advisor_history_demo/demo_summary.json`

Policy auto-tuning full chain (autotune -> governance -> advisor -> snapshot):

```bash
bash scripts/demo_policy_autotune_full_chain.sh
```

Output:
- `artifacts/policy_autotune_full_chain_demo/summary.json`

## MVP Freeze (Release Readiness)

```bash
bash scripts/mvp_freeze_check.sh
```

Outputs:
- `artifacts/mvp_freeze/summary.json`
- `artifacts/mvp_freeze/summary.md`

Fast local pre-check (targeted test scope):

```bash
bash scripts/mvp_freeze_check_fast.sh
```

Current freeze inputs:
- full unit test suite
- medium governance dashboard chain
- mutation governance dashboard chain
- policy autotune history chain
- policy autotune governance dashboard chain
- policy autotune governance advisor history chain
- governance snapshot with advisor history chain
- policy patch dashboard chain
- targeted local CI matrix

Verdict values:
- `MVP_FREEZE_PASS`
- `MVP_FREEZE_FAIL` (with `blocking_step`)

## CI (Optional Manual Jobs)

Workflow: `ci` (`workflow_dispatch`)

Set `run_benchmark=true` to run non-blocking optional chains:
- benchmark optional
- medium governance optional
- policy autotune optional
- mvp freeze optional (fast targeted mode)

Artifacts include:
- `benchmark-v0`
- `medium-governance-v1`
- `policy-autotune-governance-v1`
- `policy-autotune-governance-history-v1`
- `policy-autotune-governance-advisor-v1`
- `policy-autotune-governance-advisor-history-v1`
- `policy-autotune-full-chain-v1`
- `mvp-freeze-v1`
- `mutation-pack-v0`
- `mutation-policy-patch-v1`

## Repository Map

- `gateforge/` core commands and logic
- `benchmarks/` benchmark packs
- `examples/` Physical AI simulation examples (currently Modelica), fixtures, proposals
- `policies/` governance policy configs
- `schemas/` JSON schemas
- `scripts/` one-command demo and ops scripts
- `tests/` unit/integration tests

## More Documentation

- Detailed demo cookbook: `DEMO.md`
