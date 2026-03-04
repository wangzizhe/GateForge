# GateForge

<p align="center">
  <a href="https://github.com/wangzizhe/GateForge/actions/workflows/ci.yml" style="text-decoration:none;"><img src="https://github.com/wangzizhe/GateForge/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>&nbsp;
  <a href="https://github.com/wangzizhe/GateForge/releases" style="text-decoration:none;"><img src="https://img.shields.io/github/release/wangzizhe/GateForge.svg?include_prereleases" alt="Release" /></a>&nbsp;
  <a href="LICENSE" style="text-decoration:none;"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>&nbsp;
  <a href="https://www.python.org/" style="text-decoration:none;"><img src="https://img.shields.io/badge/python-%3E%3D3.10-3776AB.svg" alt="Python >= 3.10" /></a>
</p>
<p align="center" style="margin: 0.75rem auto 1rem; max-width: 920px; padding: 0.75rem 1rem; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa;">
  <strong>Building AI agents for physical systems with reproducible capability benchmarks.</strong>
</p>


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

Internal execution scope is maintained in `MVP_CHECKLIST.md`.

## Most Used Commands

### 1) Validate proposal

```bash
python -m gateforge.proposal_validate --in examples/proposals/proposal_v0.json
```

### 2) Run proposal

```bash
python -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
```

### 3) Regression gate only

```bash
python -m gateforge.regress \
  --baseline baselines/mock_baseline.json \
  --candidate artifacts/candidate.json \
  --out artifacts/regression.json
```

### 4) Runtime ledger demo

```bash
bash scripts/demo_runtime_decision_ledger.sh
```

### 5) Medium governance chain

```bash
bash scripts/demo_medium_pack_v1_dashboard.sh
```

### 6) Policy autotune full chain

```bash
bash scripts/demo_policy_autotune_full_chain.sh
```

## Documentation Map

- Daily demo cookbook: `DEMO.md`
- End-to-end scripts: `scripts/`
- Core modules: `gateforge/`
- Tests: `tests/`

## Non-Goals (Current)

- Full agent platform
- Full UI/SaaS product
- Multi-simulator production support (OpenModelica is current first backend)

## Legal Notice

Without prior written permission, no content on this site may be used for AI model training, fine-tuning, evaluation, or dataset construction.

- `LEGAL_NOTICE.md`
- `CONTENT_AUTHORIZATION_POLICY.md`
- `robots.txt`
