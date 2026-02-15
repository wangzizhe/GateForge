# GateForge Operations Guide

## I. Purpose

This guide defines the daily and release-time operating workflow for GateForge.
It is designed for fast failure triage, consistent governance decisions, and reproducible evidence.

## II. Daily Routine

1. Run fast local verification:
```bash
python3 -m unittest discover -s tests -q
```
2. Run local demo matrix (default profile):
```bash
bash scripts/demo_ci_matrix.sh
```
3. Check `artifacts/ci_matrix_summary.json`:
- `matrix_status`
- `failed_jobs`
- `planner_guardrail_rule_ids`
4. If matrix failed, generate repair tasks from failing summary:
```bash
python3 -m gateforge.repair_tasks --source <failing_summary.json> --out artifacts/repair_tasks/summary.json
```
5. Optional one-command repair pipeline:
```bash
python3 -m gateforge.repair_orchestrate --source <failing_summary.json> --baseline baselines/mock_minimal_probe_baseline.json --out-dir artifacts/repair_orchestrate
```
5. Prioritize repair queue from task summary:
- execute `P0` tasks first
- then `P1` evidence/fix tasks
- close with `P2` verification rerun

## III. Failure Triage

1. Determine failure layer:
- planner guardrail (`planner_guardrail_*`)
- change application / preflight (`change_apply_*`, `change_preflight_*`)
- regression checker (`*_detected`, `runtime_regression:*`)
- environment/runtime (`docker_error`, tool missing)
2. Inspect canonical evidence in this order:
- run summary
- regression summary
- candidate evidence
- policy reasons and required human checks
3. For repair-loop outputs, verify `safety_guard_triggered` is `false` before approval.
4. If status is `NEEDS_REVIEW`, require explicit reviewer resolution.

## IV. Repair Flow

1. Single-case repair:
```bash
python3 -m gateforge.repair_loop --source <fail_summary.json> --out artifacts/repair_loop/summary.json
```
2. Batch repair and profile compare:
```bash
python3 -m gateforge.repair_batch --pack <pack.json> --compare-policy-profiles default industrial_strict_v0 --continue-on-fail --summary-out artifacts/repair_batch/summary.json
```
3. Review risk deltas:
- `strict_downgrade_rate`
- `reason_distribution.delta_counts`

## V. Governance Readiness

1. Build governance snapshot:
```bash
python3 -m gateforge.governance_report --repair-batch-summary <...> --review-ledger-summary <...> --ci-matrix-summary <...> --out artifacts/governance_snapshot/summary.json
```
2. Update history and check worsening alerts:
```bash
python3 -m gateforge.governance_history --history-dir artifacts/governance_history --snapshot artifacts/governance_snapshot/summary.json --out artifacts/governance_history/summary.json
```
3. Run promotion gate:
```bash
python3 -m gateforge.governance_promote --snapshot artifacts/governance_snapshot/summary.json --profile default --out artifacts/governance_promote/summary.json
```
4. Optional human override (waiver/forced decision):
```bash
python3 -m gateforge.governance_promote --snapshot artifacts/governance_snapshot/summary.json --profile industrial_strict --override <override.json> --out artifacts/governance_promote/summary_override.json
```
5. Optional profile ranking for promotion choice:
```bash
python3 -m gateforge.governance_promote_compare --snapshot artifacts/governance_snapshot/summary.json --profiles default industrial_strict --out artifacts/governance_promote_compare/summary.json
```

## VI. Release / Push Checklist

1. Working tree clean (`git status`).
2. Local tests pass.
3. Demo matrix status is `PASS`.
4. Promotion decision is either:
- `PASS`, or
- explicitly approved `NEEDS_REVIEW` with documented rationale.
5. Commit with clear scope and push.
6. Confirm GitHub `test-and-smoke` passes.

## VII. Incident Notes Template

When incidents happen, record:

1. What changed (proposal/change_set/policy profile).
2. First failing reason.
3. Evidence paths used for diagnosis.
4. Fix applied.
5. Before/after status and policy decision.
6. Whether retry or reviewer override was used.
