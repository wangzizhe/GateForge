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
