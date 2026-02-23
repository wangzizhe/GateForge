---
name: gateforge-medium-benchmark
description: Run and validate GateForge medium benchmark pack v1 for OpenModelica Docker cases. Use when asked to execute the medium benchmark truth set, inspect pass/fail counts, or regenerate benchmark_medium_v1 summary artifacts.
---

# GateForge Medium Benchmark

Run from repository root.

## Execute

```bash
bash scripts/demo_medium_pack_v1.sh
```

## Verify

1. Read `artifacts/benchmark_medium_v1/summary.json`.
2. Confirm `pack_id=medium_pack_v1`.
3. Confirm `fail_count=0` for healthy baseline runs.
4. If `fail_count>0`, point to `mismatch_cases` and per-case `json_path`.

## Output Contract

Produce a concise status line with:
- total_cases
- pass_count
- fail_count
- pass_rate
- mismatch_case_count
