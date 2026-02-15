# GateForge Demo Index

This page gives one-command demo entry points and where to inspect results.

## 1. Proposal Flow Demo (Happy Path)

Command:

```bash
bash scripts/demo_proposal_flow.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_proposal_flow.sh
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

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_checker_config.sh
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

## 3. Steady-State Checker Demo (Behavior Drift)

Command:

```bash
bash scripts/demo_steady_state_checker.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_steady_state_checker.sh
```

What it validates:

- behavior regression checker (`steady_state_regression`)
- regression can fail even when compile/simulate status are both success

Key outputs:

- `artifacts/steady_state_demo_regression.json`
- `artifacts/steady_state_demo_summary.md`

Expected result:

- regression output contains `"decision": "NEEDS_REVIEW"` (under default medium-risk policy)
- regression reasons include:
  - `steady_state_regression_detected`

## 4. Behavior Metrics Checker Demo (Overshoot + Settling)

Command:

```bash
bash scripts/demo_behavior_metrics_checker.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_behavior_metrics_checker.sh
```

What it validates:

- combined behavior checker for control-oriented metrics
- overshoot, settling-time, and steady-state thresholds in one gate

Key outputs:

- `artifacts/behavior_metrics_demo/regression.json`
- `artifacts/behavior_metrics_demo/summary.json`
- `artifacts/behavior_metrics_demo/summary.md`

Expected result:

- regression output contains `"decision": "NEEDS_REVIEW"` (under default medium-risk policy)
- regression reasons include:
  - `overshoot_regression_detected`
  - `settling_time_regression_detected`
  - `steady_state_regression_detected`

## 5. Optional CI Demo Job

In GitHub Actions (`ci` workflow), use **Run workflow** and enable:

- `run_checker_demo=true`
- `run_steady_state_demo=true`
- `run_behavior_metrics_demo=true`
- `run_demo_bundle=true` (runs both demos, emits one summary, and is strict when triggered)
- `run_autopilot_dry_run=true` (runs dry-run review-template demo, non-blocking)
- `run_agent_change_loop=true` (runs low/high risk change safety loop demo, non-blocking)
- optional: `demo_policy_profile=industrial_strict_v0` to run all demo jobs under a profile

Artifact to download:

- `checker-config-demo`
- `steady-state-demo`
- `behavior-metrics-demo`
- `autopilot-dry-run-demo`
- `agent-change-loop-demo`

It includes all checker demo outputs including `checker_demo_summary.md`.
`steady-state-demo` includes behavior-drift regression outputs and summary.
`behavior-metrics-demo` includes overshoot/settling/steady-state checker outputs and summary.
`autopilot-dry-run-demo` includes the dry-run JSON/MD and planned human checks.
`agent-change-loop-demo` includes low/high risk summaries and policy-driven decision outcomes.
Actions job page also shows `Checker Demo Summary` (status/policy/reason counts) for quick inspection.

For combined evidence, use artifact:

- `demo-bundle` (includes `artifacts/demo_all_summary.md`)
- Actions job page also shows `Demo Bundle Summary` including reason/finding counts.

## 6. One-command bundle (local)

Command:

```bash
bash scripts/demo_all.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_all.sh
```

This runs both demos and writes:

- `artifacts/demo_all_summary.md`
- `artifacts/demo_all_summary.json` (machine-readable bundle summary)
- includes checker + steady-state + behavior-metrics expected-nonpass flags in one bundle

Batch governance view (failure distribution):

```bash
python3 -m gateforge.batch \
  --pack benchmarks/pack_v0.json \
  --out-dir artifacts/bench-pack \
  --summary-out artifacts/bench-pack/summary.json \
  --report-out artifacts/bench-pack/summary.md
cat artifacts/bench-pack/summary.json
cat artifacts/bench-pack/summary.md
```

## 7. Autopilot Dry-Run Demo (Human Review Template)

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
- you can pass profile by name: `--policy-profile industrial_strict_v0`

## 8. Repair Loop Demo (FAIL -> Repair -> Rerun)

Command:

```bash
bash scripts/demo_repair_loop.sh
```

What it validates:

- input is an existing failed governance summary
- planner/autopilot proposes a constrained repair run
- output provides before/after decision delta
- if first attempt fails, repair loop can retry once with conservative fallback constraints
- safety guard can block repaired output when new critical reasons appear

Key outputs:

- `artifacts/repair_loop/summary.json`
- `artifacts/repair_loop/summary.md`
- `artifacts/repair_loop/demo_summary.json`
- `artifacts/repair_loop/demo_summary.md`

Expected result:

- `after_status = PASS`
- `delta = improved`
- `retry_used` may be `true` when fallback retry is needed
- retry depth can be controlled with `--max-retries`

Safety-guard variant:

```bash
bash scripts/demo_repair_loop_safety_guard.sh
```

Expected result:

- `after_status = FAIL`
- `safety_guard_triggered = true`

## 9. Repair Batch Demo (Mixed Case Pack)

Command:

```bash
bash scripts/demo_repair_batch.sh
```

What it validates:

- multiple repair-loop cases in one pack
- aggregate batch summary with per-case status/delta/retry information
- mixed outcomes (at least one `PASS` and one `FAIL`) are surfaced clearly

Key outputs:

- `artifacts/repair_batch_demo/summary.json`
- `artifacts/repair_batch_demo/summary.md`
- `artifacts/repair_batch_demo/demo_summary.json`
- `artifacts/repair_batch_demo/demo_summary.md`

## 10. Repair Batch Compare Demo (Policy Profiles)

Command:

```bash
bash scripts/demo_repair_batch_compare.sh
```

What it validates:

- same repair pack executed under two policy profiles
- transition summary (`from_status -> to_status`)
- strict downgrade KPI (`strict_downgrade_rate`)
- failure-reason distribution delta across profiles

Key outputs:

- `artifacts/repair_batch_compare_demo/summary.json`
- `artifacts/repair_batch_compare_demo/summary.md`
- `artifacts/repair_batch_compare_demo/demo_summary.json`
- `artifacts/repair_batch_compare_demo/demo_summary.md`

## 10.1 Repair Tasks Demo

Command:

```bash
bash scripts/demo_repair_tasks.sh
```

What it validates:

- generates actionable repair checklist from failed run summary
- keeps policy reasons and required checks in operator-facing task form
- adds operational priority/grouping (`P0/P1/P2`, `human_review/fix_execution/...`)

Key outputs:

- `artifacts/repair_tasks_demo/summary.json`
- `artifacts/repair_tasks_demo/summary.md`
- `artifacts/repair_tasks_demo/demo_summary.json`
- `artifacts/repair_tasks_demo/demo_summary.md`

## 10.2 Repair Pack From Tasks Demo

Command:

```bash
bash scripts/demo_repair_pack_from_tasks.sh
```

What it validates:

- converts `repair_tasks` summary into executable `repair_batch` pack
- runs generated pack through repair batch and captures effectiveness counters
- applies strategy profile (`industrial_strict`) during pack generation

Key outputs:

- `artifacts/repair_pack_demo/pack.json`
- `artifacts/repair_pack_demo/summary.json`
- `artifacts/repair_pack_demo/summary.md`
- `artifacts/repair_pack_demo/demo_summary.json`
- `artifacts/repair_pack_demo/demo_summary.md`

## 10.3 Repair Orchestrate Demo

Command:

```bash
bash scripts/demo_repair_orchestrate.sh
```

What it validates:

- single-command pipeline from failed summary to batch repair outcome
- step-level exit codes and output artifacts for each stage

Key outputs:

- `artifacts/repair_orchestrate_demo/summary.json`
- `artifacts/repair_orchestrate_demo/tasks.json`
- `artifacts/repair_orchestrate_demo/pack.json`
- `artifacts/repair_orchestrate_demo/batch_summary.json`
- `artifacts/repair_orchestrate_demo/demo_summary.json`
- `artifacts/repair_orchestrate_demo/demo_summary.md`

## 10.4 Repair Orchestrate Compare Demo

Command:

```bash
bash scripts/demo_repair_orchestrate_compare.sh
```

What it validates:

- runs the same failure source through two strategy profiles (`default` vs `industrial_strict`)
- emits profile-to-profile batch status comparison (`upgraded|unchanged|downgraded`)
- emits `recommended_profile` for operator-side selection decision

Key outputs:

- `artifacts/repair_orchestrate_compare_demo/summary.json`
- `artifacts/repair_orchestrate_compare_demo/summary.md`
- `artifacts/repair_orchestrate_compare_demo/demo_summary.json`
- `artifacts/repair_orchestrate_compare_demo/demo_summary.md`

## 11. Governance Snapshot Demo

Command:

```bash
bash scripts/demo_governance_snapshot.sh
```

What it validates:

- aggregates repair compare + review ledger KPI + ci matrix into one governance decision
- emits management-facing risks and core KPI lines

Key outputs:

- `artifacts/governance_snapshot_demo/summary.json`
- `artifacts/governance_snapshot_demo/summary.md`

## 11.1 Governance Snapshot From Orchestrate Compare Demo

Command:

```bash
bash scripts/demo_governance_snapshot_from_orchestrate_compare.sh
```

What it validates:

- governance snapshot can consume `repair_orchestrate` compare summary (`strategy_compare`) directly
- snapshot emits `kpis.strategy_compare_relation` for operator visibility

Key outputs:

- `artifacts/governance_snapshot_orchestrate_demo/summary.json`
- `artifacts/governance_snapshot_orchestrate_demo/summary.md`
- `artifacts/governance_snapshot_orchestrate_demo/demo_summary.json`

## 12. Governance Snapshot Trend Demo

Command:

```bash
bash scripts/demo_governance_snapshot_trend.sh
```

What it validates:

- compares current governance snapshot with a previous one
- outputs status transition, new risks, resolved risks, and KPI deltas

Key outputs:

- `artifacts/governance_snapshot_trend_demo/previous_summary.json`
- `artifacts/governance_snapshot_trend_demo/summary.json`
- `artifacts/governance_snapshot_trend_demo/summary.md`

## 13. Governance History Demo

Command:

```bash
bash scripts/demo_governance_history.sh
```

What it validates:

- archive multiple governance snapshots into history storage
- summarize last-N status distribution and transition KPIs
- emits alert when worsening streak crosses threshold

Key outputs:

- `artifacts/governance_history_demo/history/index.jsonl`
- `artifacts/governance_history_demo/summary.json`
- `artifacts/governance_history_demo/summary.md`

## 14. Governance Promote Demo

Command:

```bash
bash scripts/demo_governance_promote.sh
```

What it validates:

- derives a promotion decision from governance snapshot
- compares default vs industrial strict promotion profile outcomes
- validates human override path (`override` can force/waive promotion)

Key outputs:

- `artifacts/governance_promote_demo/default.json`
- `artifacts/governance_promote_demo/industrial.json`
- `artifacts/governance_promote_demo/override.json`
- `artifacts/governance_promote_demo/summary.json`
- `artifacts/governance_promote_demo/summary.md`

Schema reference:

- `schemas/demo_bundle_summary.schema.json`

## 7. Local CI Matrix Demo (simulate workflow_dispatch toggles)

Command:

```bash
bash scripts/demo_ci_matrix.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_ci_matrix.sh
```

What it validates:

- local simulation of optional CI jobs
- one summary for selected jobs and exit codes

Key outputs:

- `artifacts/ci_matrix_summary.json`
- `artifacts/ci_matrix_summary.md`

Optional toggles (env vars):

- `RUN_CHECKER_DEMO=0|1`
- `RUN_STEADY_STATE_DEMO=0|1`
- `RUN_BEHAVIOR_METRICS_DEMO=0|1`
- `RUN_DEMO_BUNDLE=0|1`
- `RUN_AUTOPILOT_DRY_RUN=0|1`
- `RUN_AGENT_CHANGE_LOOP=0|1`
- `RUN_REPAIR_LOOP=0|1`
- `RUN_PLANNER_GUARDRAILS=0|1`
- `RUN_REPAIR_BATCH_DEMO=0|1`
- `RUN_REPAIR_BATCH_COMPARE_DEMO=0|1`
- `RUN_GOVERNANCE_SNAPSHOT_DEMO=0|1`
- `RUN_GOVERNANCE_SNAPSHOT_TREND_DEMO=0|1`
- `RUN_GOVERNANCE_HISTORY_DEMO=0|1`
- `RUN_BENCHMARK=0|1` (default `0`)

## 8. Agent Change Safety Loop Demo

Command:

```bash
bash scripts/demo_agent_change_loop.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_agent_change_loop.sh
```

What it validates:

- low-risk change-set can be auto-applied and executed
- high-risk change-set is blocked for human review by policy
- autopilot materializes change from planner `change_plan` into executable `change_set`

Key outputs:

- `artifacts/agent_change_loop/low_summary.json`
- `artifacts/agent_change_loop/high_summary.json`
- `artifacts/agent_change_loop/summary.json`
- `artifacts/agent_change_loop/summary.md`

## 9. Planner Confidence Gates Demo

Command:

```bash
bash scripts/demo_planner_confidence_gates.sh
```

With strict profile:

```bash
POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_planner_confidence_gates.sh
```

What it validates:

- high confidence change_plan -> `PASS`
- medium confidence change_plan -> `NEEDS_REVIEW`
- very low confidence change_plan -> `FAIL`

Key outputs:

- `artifacts/planner_confidence_demo/high.json`
- `artifacts/planner_confidence_demo/mid.json`
- `artifacts/planner_confidence_demo/low.json`
- `artifacts/planner_confidence_demo/summary.json`
- `artifacts/planner_confidence_demo/summary.md`

## 10. Planner Guardrails Demo (Format + Whitelist + Confidence)

Command:

```bash
bash scripts/demo_planner_guardrails.sh
```

What it validates:

- guarded planner output passes when confidence and file constraints are satisfied
- low-confidence planner output is rejected before execution
- planner output targeting non-whitelisted file is rejected before execution
- planner guardrail result is persisted for downstream audit (`decision + violations`)
- violations are structured with `rule_id` and `message`

Key outputs:

- `artifacts/planner_guardrails_demo/pass_intent.json`
- `artifacts/planner_guardrails_demo/summary.json`
- `artifacts/planner_guardrails_demo/summary.md`
- `summary.json` includes `rule_ids.all` (aggregated guardrail rule IDs)

### Planner Output Validation Demo (Offline Contract Check)

Command:

```bash
bash scripts/demo_planner_output_validate.sh
```

What it validates:

- valid planner output JSON passes contract checks
- malformed planner output is rejected before execution
- validation result is summarized as governance evidence

Key outputs:

- `artifacts/planner_output_validate_demo/pass_result.json`
- `artifacts/planner_output_validate_demo/fail_result.json`
- `artifacts/planner_output_validate_demo/summary.json`
- `artifacts/planner_output_validate_demo/summary.md`

## 11. Human Review Resolution Demo

Command:

```bash
bash scripts/demo_review_resolution.sh
```

What it validates:

- start from a `NEEDS_REVIEW` source summary
- human `approve` can resolve to final `PASS`
- human `reject` resolves to final `FAIL`

Key outputs:

- `artifacts/review_demo/source_needs_review.json`
- `artifacts/review_demo/review_approve.json`
- `artifacts/review_demo/review_reject.json`
- `artifacts/review_demo/final_approve.json`
- `artifacts/review_demo/final_reject.json`
- `artifacts/review_demo/summary.json`
- `artifacts/review_demo/summary.md`

## 12. Review Ledger Demo

Command:

```bash
bash scripts/demo_review_ledger.sh
```

What it validates:

- review resolution writes ledger records (JSONL)
- ledger summary aggregates PASS/FAIL and reviewer counts

Key outputs:

- `artifacts/review/ledger.jsonl`
- `artifacts/review/ledger_summary.json`
- `artifacts/review/ledger_summary.md`
- `artifacts/review_ledger_demo/ledger_summary.json`

## 12. Review Ledger Export Demo

Command:

```bash
bash scripts/demo_review_ledger_export.sh
```

What it validates:

- export ledger rows filtered by `final_status`
- export ledger rows filtered by `proposal_id`

Key outputs:

- `artifacts/review_export_demo/fail_records.json`
- `artifacts/review_export_demo/proposal_records.json`
- `artifacts/review_export_demo/fail_summary.json`
- `artifacts/review_export_demo/proposal_summary.json`

## 13. Review KPI Demo

Command:

```bash
bash scripts/demo_review_kpis.sh
```

What it validates:

- KPI summary includes approval/fail rates
- KPI summary includes risk-level distribution
- KPI summary includes last-7-days review volume
- KPI summary includes SLA breach metrics

Key outputs:

- `artifacts/review_kpi_demo/kpi_summary.json`
- `artifacts/review_kpi_demo/kpi_summary.md`
