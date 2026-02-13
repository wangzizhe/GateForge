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

- `artifacts/proposal_run_demo_mock.json`
- `artifacts/proposal_run_demo_mock.md`
- `artifacts/regression_from_proposal_demo_mock.json`

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

Artifact to download:

- `checker-config-demo`

It includes all checker demo outputs including `checker_demo_summary.md`.

