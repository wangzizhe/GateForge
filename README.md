# GateForge

GateForge is a Python toolkit for simulation governance and regression gating with reproducible evidence.

For each change, it answers:
- Did behavior regress versus baseline?
- Should this be `FAIL` or `NEEDS_REVIEW`?
- What evidence explains the decision?

## What You Get

A typical run writes both machine-readable and human-readable artifacts:
- Evidence summaries (`.json` and `.md`)
- Regression summaries (`.json` and `.md`)
- Final decision outputs (`PASS`, `FAIL`, `NEEDS_REVIEW`)

## Repository Layout

- `gateforge/`: core library + CLI entry modules
- `examples/`: sample proposals, change sets, and OpenModelica assets
- `baselines/`: baseline evidence and backend/model mapping (`index.json`)
- `policies/`: policy profiles and thresholds
- `schemas/`: JSON schemas for proposals/evidence/intent
- `scripts/`: one-command demos and workflows
- `artifacts/`: generated outputs from runs
- `DEMO.md`: demo catalog and expected results
- `OPERATIONS.md`: day-2 triage and release workflow

## Requirements

- Python `>=3.10`
- Optional: Docker Desktop (for OpenModelica-backed flows)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

## Quick Start (5 Minutes)

1. Validate a proposal:

```bash
python3 -m gateforge.proposal_validate \
  --in examples/proposals/proposal_v0.json
```

2. Run the end-to-end proposal flow with automatic baseline resolution:

```bash
python3 -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
```

3. Inspect outputs:

```bash
cat artifacts/proposal_run.json
cat artifacts/proposal_run.md
cat artifacts/regression_from_proposal.json
```

## Common Workflows

### Fast Local Validation Matrix

```bash
bash scripts/demo_ci_matrix.sh
cat artifacts/ci_matrix_summary.json
```

### Proposal and Regression Demos

- `bash scripts/demo_proposal_flow.sh`
- `bash scripts/demo_checker_config.sh`
- `bash scripts/demo_steady_state_checker.sh`
- `bash scripts/demo_behavior_metrics_checker.sh`

### Repair and Orchestration

- `bash scripts/demo_repair_tasks.sh`
- `bash scripts/demo_repair_loop.sh`
- `bash scripts/demo_repair_batch.sh`
- `bash scripts/demo_repair_orchestrate.sh`

### Governance and Promotion

- `bash scripts/demo_governance_snapshot.sh`
- `bash scripts/demo_governance_history.sh`
- `bash scripts/demo_governance_promote.sh`
- `bash scripts/demo_governance_promote_compare.sh`
- `bash scripts/demo_governance_promote_apply.sh`

### Agent and Planner Guardrails

- `bash scripts/demo_agent_change_loop.sh`
- `bash scripts/demo_agent_invariant_guard.sh`
- `bash scripts/demo_autopilot_dry_run.sh`
- `bash scripts/demo_planner_guardrails.sh`
- `bash scripts/demo_planner_output_validate.sh`

Run all bundled demos:

```bash
bash scripts/demo_all.sh
```

## Policy Profiles

By default, commands resolve policy from `policies/`.

Run with a stricter profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_all.sh
```

Several governance and repair commands also accept explicit profile arguments.

## CLI Modules

Use `--help` on any module for exact options.

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

## OpenModelica Support (Optional)

To run OpenModelica-backed flows, pull the tested container image:

```bash
docker pull openmodelica/openmodelica:v1.26.1-minimal
```

You can then run proposals or smoke/regression flows configured for Docker/OpenModelica.

## Troubleshooting

- `docker_error`: start Docker Desktop and verify `docker ps` works.
- `--baseline auto` resolution failure: verify mapping in `baselines/index.json`.
- `NEEDS_REVIEW` decision: resolve with `python3 -m gateforge.review_resolve` and persist via review ledger tools.

## Documentation

- Demo catalog: `DEMO.md`
- Operations guide: `OPERATIONS.md`
- License: `LICENSE`
