# GateForge

GateForge is a Python toolkit for running simulation governance checks with reproducible evidence.

It helps answer:
- Did this change regress behavior compared to baseline?
- Is the result a hard fail, or does it need human review?
- What artifacts explain that decision?

## What GateForge Produces

For each run, GateForge writes machine- and human-readable outputs:
- Evidence JSON/Markdown
- Regression JSON/Markdown
- Run summary JSON/Markdown

Typical status outcomes:
- `PASS`
- `FAIL`
- `NEEDS_REVIEW`

## Repository Map

- `gateforge/`: core modules and CLI entry points
- `examples/`: sample proposals, models, and change sets
- `baselines/`: baseline evidence and index mapping
- `policies/`: policy and profile configuration
- `schemas/`: JSON schemas for proposal/evidence/intent outputs
- `scripts/`: one-command demo scripts
- `artifacts/`: generated outputs
- `DEMO.md`: full demo catalog
- `OPERATIONS.md`: day-2 operations and triage workflow

## Requirements

- Python `>=3.10`
- (Optional) Docker Desktop for OpenModelica-backed runs

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

## Quick Start (Mock Backend)

Validate a proposal:

```bash
python3 -m gateforge.proposal_validate \
  --in examples/proposals/proposal_v0.json
```

Run proposal pipeline with automatic baseline resolution:

```bash
python3 -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
```

Inspect outputs:

```bash
cat artifacts/proposal_run.json
cat artifacts/proposal_run.md
cat artifacts/regression_from_proposal.json
```

## One-Command Demos

These scripts are the fastest way to see specific behaviors.

- Full proposal flow: `bash scripts/demo_proposal_flow.sh`
- Checker thresholds: `bash scripts/demo_checker_config.sh`
- Steady-state drift: `bash scripts/demo_steady_state_checker.sh`
- Behavior metrics: `bash scripts/demo_behavior_metrics_checker.sh`
- Repair loop: `bash scripts/demo_repair_loop.sh`
- Governance snapshot/promote demos: see `DEMO.md`

Run the local demo matrix:

```bash
bash scripts/demo_ci_matrix.sh
cat artifacts/ci_matrix_summary.json
```

## Policy Profiles

Default behavior uses policy files under `policies/`.

Run with strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_all.sh
```

Or pass profile flags on profile-aware commands (for example `governance_promote_compare`, `repair_batch`, and related orchestration flows).

## Common CLI Commands

Core flow:
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
- `python3 -m gateforge.review_resolve`
- `python3 -m gateforge.review_ledger`
- `python3 -m gateforge.governance_report`
- `python3 -m gateforge.governance_history`
- `python3 -m gateforge.governance_promote`
- `python3 -m gateforge.governance_promote_compare`
- `python3 -m gateforge.governance_promote_apply`

Planner/invariant tools:
- `python3 -m gateforge.llm_planner`
- `python3 -m gateforge.planner_output_validate`
- `python3 -m gateforge.invariant_repair`
- `python3 -m gateforge.invariant_repair_compare`

Tip: add `--help` to any command for full arguments.

## Optional OpenModelica Backend

If you want OpenModelica-backed execution, pull the image used by the project demos:

```bash
docker pull openmodelica/openmodelica:v1.26.1-minimal
```

Then run smoke/proposal flows with backend settings from your proposal files.

## Troubleshooting

- `docker_error`: start Docker Desktop and verify `docker ps` works.
- Baseline resolution failures with `--baseline auto`:
  - confirm model/backend mapping exists in `baselines/index.json`.
- `NEEDS_REVIEW` outcomes:
  - use `gateforge.review_resolve` and persist decisions to the review ledger.

## Additional Docs

- Demo walkthroughs: `DEMO.md`
- Operating playbook: `OPERATIONS.md`
- License: `LICENSE`
