# GateForge

GateForge is a Python toolkit for simulation governance and regression gating with reproducible evidence.

It answers three practical questions for each change:
- Did behavior regress vs baseline?
- Is this a hard fail or `NEEDS_REVIEW`?
- What evidence explains the decision?

## Core Outputs

A typical run writes both machine-readable and human-readable artifacts:
- Evidence JSON/Markdown
- Regression JSON/Markdown
- Run summary JSON/Markdown

Standard decisions:
- `PASS`
- `FAIL`
- `NEEDS_REVIEW`

## Project Layout

- `gateforge/`: core modules and CLI entry points
- `examples/`: sample proposals, model scripts, and change sets
- `baselines/`: baseline evidence and backend/model mapping (`index.json`)
- `policies/`: policy profiles and thresholds
- `schemas/`: proposal/evidence/intent JSON schemas
- `scripts/`: one-command local demos
- `artifacts/`: generated outputs
- `DEMO.md`: demo catalog and expected results
- `OPERATIONS.md`: day-2 triage and release workflow

## Requirements

- Python `>=3.10`
- Optional: Docker Desktop for OpenModelica-backed execution

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify with tests:

```bash
python3 -m unittest discover -s tests -v
```

## 5-Minute Quick Start

1. Validate a proposal:

```bash
python3 -m gateforge.proposal_validate \
  --in examples/proposals/proposal_v0.json
```

2. Run end-to-end proposal flow with automatic baseline resolution:

```bash
python3 -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
```

3. Inspect generated artifacts:

```bash
cat artifacts/proposal_run.json
cat artifacts/proposal_run.md
cat artifacts/regression_from_proposal.json
```

## Fastest Demo Paths

Run one script depending on what you want to validate:
- Happy-path proposal flow: `bash scripts/demo_proposal_flow.sh`
- Checker threshold gating: `bash scripts/demo_checker_config.sh`
- Steady-state drift detection: `bash scripts/demo_steady_state_checker.sh`
- Behavior metrics (overshoot/settling): `bash scripts/demo_behavior_metrics_checker.sh`
- Repair loop orchestration: `bash scripts/demo_repair_loop.sh`

Run the local matrix:

```bash
bash scripts/demo_ci_matrix.sh
cat artifacts/ci_matrix_summary.json
```

See `DEMO.md` for the full demo set and expected outcomes.

## Policy Profiles

By default, commands resolve policy from `policies/`.

Run demos with a stricter profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_all.sh
```

Many governance/repair commands also accept explicit profile arguments (for example: `repair_batch`, `governance_promote`, `governance_promote_compare`).

## CLI Reference

Use `--help` on any command for argument details.

Core execution:
- `python3 -m gateforge.proposal_validate`
- `python3 -m gateforge.smoke`
- `python3 -m gateforge.regress`
- `python3 -m gateforge.run`
- `python3 -m gateforge.batch`

Automation and repair:
- `python3 -m gateforge.agent`
- `python3 -m gateforge.agent_run`
- `python3 -m gateforge.autopilot`
- `python3 -m gateforge.repair_tasks`
- `python3 -m gateforge.repair_pack`
- `python3 -m gateforge.repair_loop`
- `python3 -m gateforge.repair_batch`
- `python3 -m gateforge.repair_orchestrate`

Governance and review:
- `python3 -m gateforge.review`
- `python3 -m gateforge.review_resolve`
- `python3 -m gateforge.review_ledger`
- `python3 -m gateforge.governance_report`
- `python3 -m gateforge.governance_history`
- `python3 -m gateforge.governance_promote`
- `python3 -m gateforge.governance_promote_compare`
- `python3 -m gateforge.governance_promote_apply`

Planner and invariant tools:
- `python3 -m gateforge.llm_planner`
- `python3 -m gateforge.planner_output_validate`
- `python3 -m gateforge.invariant_repair`
- `python3 -m gateforge.invariant_repair_compare`

## Optional OpenModelica Backend

To run OpenModelica-backed flows:

```bash
docker pull openmodelica/openmodelica:v1.26.1-minimal
```

Then run smoke/proposal flows configured for Docker/OpenModelica in proposal inputs.

## Troubleshooting

- `docker_error`: start Docker Desktop and confirm `docker ps` works.
- `--baseline auto` resolution fails:
  - check `baselines/index.json` for a matching backend/model mapping.
- `NEEDS_REVIEW` decisions:
  - resolve with `gateforge.review_resolve` and persist to review ledger.

## More Docs

- Demo catalog: `DEMO.md`
- Operations guide: `OPERATIONS.md`
- License: `LICENSE`
