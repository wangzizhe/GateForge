# GateForge Demo Index

This page gives one-command demo entry points and where to inspect results.

## 1. Proposal Flow Demo (Happy Path)

Command:

```bash
bash scripts/demo_proposal_flow.sh
```

What it validates:

- proposal -> run -> regress full path
- status should be `PASS`

Key outputs:

- `artifacts/proposal_run_demo.json`
- `artifacts/proposal_run_demo.md`
- `artifacts/regression_from_proposal_demo.json`

Expected result:

- run summary contains `"status": "PASS"`
- regression decision is `PASS`

## 2. Checker Config Demo (Governance Thresholds)

Command:

```bash
bash scripts/demo_checker_config.sh
```

What it validates:

- proposal-driven checker selection
- configurable checker thresholds (`checker_config`)
- structured reasons/findings for gate failure

Key outputs:

- `artifacts/checker_demo_run.json`
- `artifacts/checker_demo_regression.json`
- `artifacts/checker_demo_summary.md`

Expected result:

- run summary contains `"status": "FAIL"`
- regression reasons include:
  - `performance_regression_detected`
  - `event_explosion_detected`

## 3. Optional CI Demo Job

In GitHub Actions (`ci` workflow), use **Run workflow** and enable:

- `run_checker_demo=true`
- `run_demo_bundle=true` (runs both demos, emits one summary, and is strict when triggered)
- `run_autopilot_dry_run=true` (runs dry-run review-template demo, non-blocking)

Artifact to download:

- `checker-config-demo`
- `autopilot-dry-run-demo`

It includes all checker demo outputs including `checker_demo_summary.md`.
`autopilot-dry-run-demo` includes the dry-run JSON/MD and planned human checks.
Actions job page also shows `Checker Demo Summary` (status/policy/reason counts) for quick inspection.

For combined evidence, use artifact:

- `demo-bundle` (includes `artifacts/demo_all_summary.md`)
- Actions job page also shows `Demo Bundle Summary` including reason/finding counts.

## 4. One-command bundle (local)

Command:

```bash
bash scripts/demo_all.sh
```

This runs both demos and writes:

- `artifacts/demo_all_summary.md`
- `artifacts/demo_all_summary.json` (machine-readable bundle summary)

## 5. Autopilot Dry-Run Demo (Human Review Template)

Command:

```bash
bash scripts/demo_autopilot_dry_run.sh
```

What it validates:

- planner + autopilot plan-only path
- `planned_risk_level` and `planned_required_human_checks`

Key outputs:

- `artifacts/autopilot/autopilot_dry_run_demo.json`
- `artifacts/autopilot/autopilot_dry_run_demo.md`

Policy profiles (optional):

- default: `policies/default_policy.json`
- strict: `policies/profiles/industrial_strict_v0.json`

Schema reference:

- `schemas/demo_bundle_summary.schema.json`
