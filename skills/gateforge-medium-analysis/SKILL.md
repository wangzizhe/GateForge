---
name: gateforge-medium-analysis
description: Analyze GateForge medium benchmark mismatches and rank debugging priorities. Use when medium benchmark summary exists and the user asks why cases failed or what to fix first.
---

# GateForge Medium Analysis

Run from repository root.

## Execute

```bash
python3 -m gateforge.medium_benchmark_analyze \
  --summary artifacts/benchmark_medium_v1/summary.json \
  --out artifacts/benchmark_medium_v1/analysis.json \
  --report-out artifacts/benchmark_medium_v1/analysis.md
```

## Interpret

1. Read `mismatch_key_counts`.
2. Read `recommendations` sorted by count.
3. Report top 3 mismatch keys with priorities.

## Output Contract

Return:
- top mismatch keys and counts
- first recommended fix action
- whether analysis indicates taxonomy/gate/parser drift
