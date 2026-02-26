# GateForge Demo Cookbook (Condensed)

This is the short demo index for daily use.

## 0. Environment

Run from repo root. Ensure Python env is active.

```bash
python -m unittest discover -s tests -v
```

## 1. Minimal Proposal Flow

```bash
bash scripts/demo_proposal_flow.sh
cat artifacts/proposal_flow_summary.json
```

## 2. Runtime Decision Ledger Governance

### 2.1 Runtime ledger

```bash
bash scripts/demo_runtime_decision_ledger.sh
cat artifacts/runtime_decision_ledger_demo/summary.json
```

### 2.2 Runtime ledger trend

```bash
bash scripts/demo_runtime_decision_ledger_trend.sh
cat artifacts/runtime_decision_ledger_trend_demo/summary.json
```

### 2.3 Runtime history + governance snapshot linkage

```bash
bash scripts/demo_runtime_decision_ledger_history.sh
cat artifacts/runtime_decision_ledger_history_demo/summary.json

bash scripts/demo_governance_runtime_history.sh
cat artifacts/governance_runtime_history_demo/summary.json
```

## 3. Medium Governance Mainline

### 3.1 Medium benchmark truth set

```bash
bash scripts/demo_medium_pack_v1.sh
cat artifacts/benchmark_medium_v1/summary.json
```

### 3.2 Mismatch analysis

```bash
bash scripts/demo_medium_pack_v1_analysis.sh
cat artifacts/benchmark_medium_v1/analysis.json
```

### 3.3 History alerts

```bash
bash scripts/demo_medium_pack_v1_history.sh
cat artifacts/benchmark_medium_v1/history_summary.json
```

### 3.4 Trend + advisor + dashboard

```bash
bash scripts/demo_medium_pack_v1_dashboard.sh
cat artifacts/benchmark_medium_v1/history_trend.json
cat artifacts/benchmark_medium_v1/advisor.json
cat artifacts/benchmark_medium_v1/dashboard.json
```

## 4. Policy Patch Governance

### 4.1 Patch apply flow

```bash
bash scripts/demo_governance_policy_patch_apply.sh
cat artifacts/governance_policy_patch_apply_demo/summary.json
```

### 4.2 Patch history flow

```bash
bash scripts/demo_governance_policy_patch_history.sh
cat artifacts/governance_policy_patch_history_demo/demo_summary.json
```

### 4.3 Patch dashboard flow

```bash
bash scripts/demo_governance_policy_patch_dashboard.sh
cat artifacts/governance_policy_patch_dashboard_demo/demo_summary.json
```

## 5. Agent / Planner Governance

### 5.1 Agent change safety loop

```bash
bash scripts/demo_agent_change_loop.sh
cat artifacts/agent_change_loop/summary.json
```

### 5.2 Planner confidence gates

```bash
bash scripts/demo_planner_confidence_gates.sh
cat artifacts/planner_confidence_demo/summary.json
```

### 5.3 Planner guardrails

```bash
bash scripts/demo_planner_guardrails.sh
cat artifacts/planner_guardrails_demo/summary.json
```

## 6. Repair Loop Governance

### 6.1 Repair loop

```bash
bash scripts/demo_repair_loop.sh
cat artifacts/repair_loop/demo_summary.json
```

### 6.2 Safety guard

```bash
bash scripts/demo_repair_loop_safety_guard.sh
cat artifacts/repair_loop_safety_demo/demo_summary.json
```

## 7. Local CI Matrix Simulation

```bash
bash scripts/demo_ci_matrix.sh
cat artifacts/ci_matrix_summary.json
```

Targeted matrix (faster):

```bash
bash scripts/demo_ci_matrix.sh --none --checker-demo --autopilot-dry-run --governance-policy-patch-dashboard-demo
cat artifacts/ci_matrix_summary.json
```

Policy autotune full-chain only:

```bash
bash scripts/demo_ci_matrix.sh --none --policy-autotune-full-chain-demo
cat artifacts/ci_matrix_summary.json
```

## 8. MVP Freeze Check

```bash
bash scripts/mvp_freeze_check.sh
cat artifacts/mvp_freeze/summary.json
cat artifacts/mvp_freeze/summary.md
```

Fast pre-check (targeted tests + full governance chains):

```bash
bash scripts/mvp_freeze_check_fast.sh
cat artifacts/mvp_freeze/summary.json
```

Verdict:
- `MVP_FREEZE_PASS`
- `MVP_FREEZE_FAIL` (with `blocking_step`)

## 9. Policy Auto-Tune Full Chain

```bash
bash scripts/demo_policy_autotune_full_chain.sh
cat artifacts/policy_autotune_full_chain_demo/summary.json
```

## 10. Optional CI (GitHub Actions)

Workflow: `ci` (`workflow_dispatch`)

Common toggles:
- `run_benchmark=true` -> `benchmark-optional`, `dataset-pipeline-optional`, `mvp-freeze-optional`
- `run_governance_snapshot_demo=true` -> `medium-governance-optional`
- `run_governance_history_demo=true` -> `policy-autotune-optional`, `runtime-governance-history-optional`

## 11. Dataset Pipeline (Build + Freeze)

```bash
bash scripts/demo_dataset_pipeline.sh
cat artifacts/dataset_pipeline_demo/summary.json
```

This demo now includes:
- dataset build
- dataset quality gate
- dataset freeze

Artifacts-driven mode (collect from existing `artifacts/` first):

```bash
bash scripts/demo_dataset_artifacts_pipeline.sh
cat artifacts/dataset_artifacts_pipeline_demo/summary.json
```

## 12. Dataset History + Trend

```bash
bash scripts/demo_dataset_history.sh
cat artifacts/dataset_history_demo/summary.json
```

## 13. Dataset Governance (Advisor + Patch Proposal)

```bash
bash scripts/demo_dataset_governance.sh
cat artifacts/dataset_governance_demo/summary.json
```

## 14. Dataset Policy Lifecycle (Apply + Ledger + Effectiveness)

```bash
bash scripts/demo_dataset_policy_lifecycle.sh
cat artifacts/dataset_policy_lifecycle_demo/summary.json
```

## 15. Dataset Governance History Trend

```bash
bash scripts/demo_dataset_governance_history.sh
cat artifacts/dataset_governance_history_demo/summary.json
```

## 16. Dataset Strategy Auto-Tune Advisor

```bash
bash scripts/demo_dataset_strategy_autotune.sh
cat artifacts/dataset_strategy_autotune_demo/summary.json
```

## 17. Dataset Governance Snapshot

```bash
bash scripts/demo_dataset_governance_snapshot.sh
cat artifacts/dataset_governance_snapshot_demo/demo_summary.json
```

## 17.1 Dataset Failure Taxonomy Coverage

```bash
bash scripts/demo_dataset_failure_taxonomy_coverage.sh
cat artifacts/dataset_failure_taxonomy_coverage_demo/demo_summary.json
```

## 17.2 Dataset Failure Distribution Benchmark

```bash
bash scripts/demo_dataset_failure_distribution_benchmark.sh
cat artifacts/dataset_failure_distribution_benchmark_demo/demo_summary.json
```

## 17.3 Dataset Model Scale Ladder

```bash
bash scripts/demo_dataset_model_scale_ladder.sh
cat artifacts/dataset_model_scale_ladder_demo/demo_summary.json
```

## 17.4 Dataset Failure Policy Patch Advisor

```bash
bash scripts/demo_dataset_failure_policy_patch_advisor.sh
cat artifacts/dataset_failure_policy_patch_advisor_demo/demo_summary.json
```

## 17.5 Dataset Governance Evidence Pack

```bash
bash scripts/demo_dataset_governance_evidence_pack.sh
cat artifacts/dataset_governance_evidence_pack_demo/demo_summary.json
```

## 17.6 Dataset Failure Corpus Registry

```bash
bash scripts/demo_dataset_failure_corpus_registry.sh
cat artifacts/dataset_failure_corpus_registry_demo/demo_summary.json
```

## 17.7 Dataset Blind Spot Backlog

```bash
bash scripts/demo_dataset_blind_spot_backlog.sh
cat artifacts/dataset_blind_spot_backlog_demo/demo_summary.json
```

## 17.8 Dataset Policy Patch Replay Evaluator

```bash
bash scripts/demo_dataset_policy_patch_replay_evaluator.sh
cat artifacts/dataset_policy_patch_replay_evaluator_demo/demo_summary.json
```

## 17.9 Dataset Moat Trend Snapshot

```bash
bash scripts/demo_dataset_moat_trend_snapshot.sh
cat artifacts/dataset_moat_trend_snapshot_demo/demo_summary.json
```

## 17.10 Dataset Backlog Execution Bridge

```bash
bash scripts/demo_dataset_backlog_execution_bridge.sh
cat artifacts/dataset_backlog_execution_bridge_demo/demo_summary.json
```

## 17.11 Dataset Replay Quality Guard

```bash
bash scripts/demo_dataset_replay_quality_guard.sh
cat artifacts/dataset_replay_quality_guard_demo/demo_summary.json
```

## 17.12 Dataset Failure Coverage Planner

```bash
bash scripts/demo_dataset_failure_coverage_planner.sh
cat artifacts/dataset_failure_coverage_planner_demo/demo_summary.json
```

## 17.13 Dataset Policy Experiment Runner

```bash
bash scripts/demo_dataset_policy_experiment_runner.sh
cat artifacts/dataset_policy_experiment_runner_demo/demo_summary.json
```

## 17.14 Dataset Modelica Failure Pack Planner

```bash
bash scripts/demo_dataset_modelica_failure_pack_planner.sh
cat artifacts/dataset_modelica_failure_pack_planner_demo/demo_summary.json
```

## 17.15 Dataset Moat Execution Forecast

```bash
bash scripts/demo_dataset_moat_execution_forecast.sh
cat artifacts/dataset_moat_execution_forecast_demo/demo_summary.json
```

## 17.16 Dataset Pack Execution Tracker

```bash
bash scripts/demo_dataset_pack_execution_tracker.sh
cat artifacts/dataset_pack_execution_tracker_demo/demo_summary.json
```

## 17.17 Dataset Large Model Failure Queue

```bash
bash scripts/demo_dataset_large_model_failure_queue.sh
cat artifacts/dataset_large_model_failure_queue_demo/demo_summary.json
```

## 17.18 Dataset Failure Signal Calibrator

```bash
bash scripts/demo_dataset_failure_signal_calibrator.sh
cat artifacts/dataset_failure_signal_calibrator_demo/demo_summary.json
```

## 17.19 Dataset Governance Decision Proofbook

```bash
bash scripts/demo_dataset_governance_decision_proofbook.sh
cat artifacts/dataset_governance_decision_proofbook_demo/demo_summary.json
```

## 17.20 Dataset Large Model Campaign Board

```bash
bash scripts/demo_dataset_large_model_campaign_board.sh
cat artifacts/dataset_large_model_campaign_board_demo/demo_summary.json
```

## 17.21 Dataset Failure Supply Plan

```bash
bash scripts/demo_dataset_failure_supply_plan.sh
cat artifacts/dataset_failure_supply_plan_demo/demo_summary.json
```

## 17.22 Dataset Model Scale Mix Guard

```bash
bash scripts/demo_dataset_model_scale_mix_guard.sh
cat artifacts/dataset_model_scale_mix_guard_demo/demo_summary.json
```

## 17.23 Dataset Governance Evidence Release Manifest

```bash
bash scripts/demo_dataset_governance_evidence_release_manifest.sh
cat artifacts/dataset_governance_evidence_release_manifest_demo/demo_summary.json
```

## 17.24 Dataset External Proof Score

```bash
bash scripts/demo_dataset_external_proof_score.sh
cat artifacts/dataset_external_proof_score_demo/demo_summary.json
```

## 18. Dataset Policy Auto-Tune History

```bash
bash scripts/demo_dataset_policy_autotune_history.sh
cat artifacts/dataset_policy_autotune_history_demo/summary.json
```

## 19. Dataset Governance Snapshot Trend

```bash
bash scripts/demo_dataset_governance_snapshot_trend.sh
cat artifacts/dataset_governance_snapshot_trend_demo/demo_summary.json
```

The demo summary now includes severity fields:
- `severity_score`
- `severity_level`
- `promotion_effectiveness_history_trend_transition`

## 20. Dataset Strategy Auto-Tune Apply

```bash
bash scripts/demo_dataset_strategy_autotune_apply.sh
cat artifacts/dataset_strategy_autotune_apply_demo/summary.json
```

## 21. Dataset Strategy Auto-Tune Apply History

```bash
bash scripts/demo_dataset_strategy_autotune_apply_history.sh
cat artifacts/dataset_strategy_autotune_apply_history_demo/summary.json
```

## 22. Dataset Optional CI Contract Check

```bash
python3 -m gateforge.dataset_optional_ci_contract \
  --artifacts-root artifacts \
  --out artifacts/dataset_optional_ci_contract/summary.json \
  --report-out artifacts/dataset_optional_ci_contract/summary.md
cat artifacts/dataset_optional_ci_contract/summary.json
```

One-shot full contract demo:

```bash
bash scripts/demo_dataset_optional_ci_contract.sh
cat artifacts/dataset_optional_ci_contract_demo/demo_summary.json
```

## 23. Dataset Promotion Candidate Advisor

```bash
bash scripts/demo_dataset_promotion_candidate.sh
cat artifacts/dataset_promotion_candidate_demo/summary.json
```

## 24. Dataset Promotion Candidate History

```bash
bash scripts/demo_dataset_promotion_candidate_history.sh
cat artifacts/dataset_promotion_candidate_history_demo/summary.json
```

## 25. Dataset Promotion Candidate Apply

```bash
bash scripts/demo_dataset_promotion_candidate_apply.sh
cat artifacts/dataset_promotion_candidate_apply_demo/summary.json
```

## 26. Dataset Promotion Candidate Apply History

```bash
bash scripts/demo_dataset_promotion_candidate_apply_history.sh
cat artifacts/dataset_promotion_candidate_apply_history_demo/summary.json
```

## 27. Dataset Promotion Effectiveness

```bash
bash scripts/demo_dataset_promotion_effectiveness.sh
cat artifacts/dataset_promotion_effectiveness_demo/summary.json
```

## 28. Dataset Promotion Effectiveness History + Trend

```bash
bash scripts/demo_dataset_promotion_effectiveness_history.sh
cat artifacts/dataset_promotion_effectiveness_history_demo/summary.json
```
