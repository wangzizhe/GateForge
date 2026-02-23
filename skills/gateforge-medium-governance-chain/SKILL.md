---
name: gateforge-medium-governance-chain
description: Run the full medium governance chain in GateForge (benchmark, analysis, history, trend, advisor, dashboard). Use when asked for an end-to-end medium governance health check.
---

# GateForge Medium Governance Chain

Run from repository root.

## Execute Full Chain

```bash
bash scripts/demo_medium_pack_v1_dashboard.sh
```

## Validate Core Artifacts

1. `artifacts/benchmark_medium_v1/summary.json`
2. `artifacts/benchmark_medium_v1/analysis.json`
3. `artifacts/benchmark_medium_v1/history_summary.json`
4. `artifacts/benchmark_medium_v1/history_trend.json`
5. `artifacts/benchmark_medium_v1/advisor.json`
6. `artifacts/benchmark_medium_v1/dashboard.json`

## Decision Output

Report:
- dashboard `bundle_status`
- advisor `decision` and `suggested_profile`
- trend `delta_pass_rate`
- mismatch_case_count
