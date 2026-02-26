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

GateForge is a decision gate around model changes, not a modeling copilot.

Flow: `proposal -> run -> evidence -> regress -> policy -> review`

Current scope: Modelica workflows as the first Physical AI pressure-test domain.

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

## MVP Scope (Current)

- Proposal schema + validation
- Run pipeline with structured evidence output
- Regression gate with strict comparability controls
- Policy engine: `PASS` / `NEEDS_REVIEW` / `FAIL`
- Human review resolution path
- Agent/autopilot entrypoints with guarded execution
- Runtime decision ledger + history + trend
- Governance snapshot/report from multi-source signals
- Failure taxonomy coverage ledger (failure type / model scale / stage)
- Failure distribution benchmark (detection/false-positive/regression/drift)
- Model scale ladder (small/medium/large readiness + CI lane recommendation)
- Failure policy patch advisor (evidence-driven policy tightening suggestions)
- Governance evidence pack (externally shareable proof artifact)
- Failure corpus registry (stable IDs, fingerprints, corpus versioning)
- Blind-spot backlog generator (prioritized coverage gap tasks)
- Policy patch replay evaluator (before/after patch impact scoring)
- Governance evidence pack v2 (action-outcome + policy ROI context)
- Moat trend snapshot (time-series moat metrics and deltas)
- Backlog execution bridge (convert blind spots to ready execution tasks)
- Replay quality guard (sample-size and stability checks for replay conclusions)
- Failure coverage planner (prioritized coverage plan with expected moat deltas)
- Policy experiment runner (ranked conservative/balanced/aggressive policy experiments)
- Modelica failure pack planner (scale-aware case targets for small/medium/large packs)
- Moat execution forecast (30-day moat projection from pack + experiment execution plans)
- Pack execution tracker (execution progress and large-scale completion visibility)
- Large model failure queue (priority queue for large-scale failure gap closure)
- Failure signal calibrator (adaptive weighting for detection/fp/regression/drift signals)
- Governance decision proofbook (compact decision-ready evidence cards)
- Large model campaign board (weekly execution board for large-scale closure)
- Failure supply plan (weekly failure-case supply targets and channels)
- Model scale mix guard (ratio guardrail for medium/large dataset share)
- Governance evidence release manifest (externally shareable proof artifact manifest)
- External proof score (single score for external evidence strength communication)
- Failure corpus DB v1 (normalized failure-case database with reproducibility metadata)
- Failure baseline pack v1 (fixed reproducible small/medium/large baseline slice)
- Failure distribution quality gate v1 (baseline distribution and diversity quality guard)
- Anchor benchmark artifact v1 (externally shareable reproducible benchmark anchor)
- Modelica library registry v1 (checksummed model inventory with complexity metadata)
- Model family generator v1 (derive small/medium/large family manifests from registry assets)
- Mutation factory v1 (deterministic mutation manifest with multi-failure-type operators)
- Repro stability gate v1 (repeat-run consistency gate for mutation reproducibility)
- Failure corpus ingest bridge v1 (ingest stable mutation evidence into failure corpus DB v1)
- Anchor benchmark pack v2 (end-to-end reproducible anchor pack from baseline+mutation+stability)

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
