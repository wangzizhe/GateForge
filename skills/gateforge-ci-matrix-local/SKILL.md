---
name: gateforge-ci-matrix-local
description: Run GateForge local CI demo matrix and summarize optional-job health before push. Use when asked for a fast local equivalent of optional workflow_dispatch jobs.
---

# GateForge Local CI Matrix

Run from repository root.

## Execute

```bash
bash scripts/demo_ci_matrix.sh
```

## Validate

1. Read `artifacts/ci_matrix_summary.json`.
2. Confirm `matrix_status`.
3. If failed, list `failed_jobs` and map each to `artifacts/ci_matrix_logs/<job>.log`.

## Focus Flags

Use selective flags for targeted checks:
- `--none` to disable defaults
- `--governance-policy-patch-dashboard-demo` to run only that module block
- `--benchmark` for benchmark path
