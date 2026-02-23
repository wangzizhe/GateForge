# GateForge Demo Cookbook (Condensed)

This is the short demo index for daily use.

For historical/full demo catalog, see:
- `docs/legacy-demo.md`

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

## 2. Medium Governance Mainline

### 2.1 Medium benchmark truth set

```bash
bash scripts/demo_medium_pack_v1.sh
cat artifacts/benchmark_medium_v1/summary.json
```

### 2.2 Mismatch analysis

```bash
bash scripts/demo_medium_pack_v1_analysis.sh
cat artifacts/benchmark_medium_v1/analysis.json
```

### 2.3 History alerts

```bash
bash scripts/demo_medium_pack_v1_history.sh
cat artifacts/benchmark_medium_v1/history_summary.json
```

### 2.4 Trend + advisor + dashboard

```bash
bash scripts/demo_medium_pack_v1_dashboard.sh
cat artifacts/benchmark_medium_v1/history_trend.json
cat artifacts/benchmark_medium_v1/advisor.json
cat artifacts/benchmark_medium_v1/dashboard.json
```

## 3. Policy Patch Governance

### 3.1 Patch apply flow

```bash
bash scripts/demo_governance_policy_patch_apply.sh
cat artifacts/governance_policy_patch_apply_demo/summary.json
```

### 3.2 Patch history flow

```bash
bash scripts/demo_governance_policy_patch_history.sh
cat artifacts/governance_policy_patch_history_demo/demo_summary.json
```

### 3.3 Patch dashboard flow

```bash
bash scripts/demo_governance_policy_patch_dashboard.sh
cat artifacts/governance_policy_patch_dashboard_demo/demo_summary.json
```

## 4. Agent / Planner Governance

### 4.1 Agent change safety loop

```bash
bash scripts/demo_agent_change_loop.sh
cat artifacts/agent_change_loop/summary.json
```

### 4.2 Planner confidence gates

```bash
bash scripts/demo_planner_confidence_gates.sh
cat artifacts/planner_confidence_demo/summary.json
```

### 4.3 Planner guardrails

```bash
bash scripts/demo_planner_guardrails.sh
cat artifacts/planner_guardrails_demo/summary.json
```

## 5. Repair Loop Governance

### 5.1 Repair loop

```bash
bash scripts/demo_repair_loop.sh
cat artifacts/repair_loop/demo_summary.json
```

### 5.2 Safety guard

```bash
bash scripts/demo_repair_loop_safety_guard.sh
cat artifacts/repair_loop_safety_demo/demo_summary.json
```

## 6. Local CI Matrix Simulation

```bash
bash scripts/demo_ci_matrix.sh
cat artifacts/ci_matrix_summary.json
```

Targeted matrix (faster):

```bash
bash scripts/demo_ci_matrix.sh --none --checker-demo --autopilot-dry-run --governance-policy-patch-dashboard-demo
cat artifacts/ci_matrix_summary.json
```

## 7. MVP Freeze Check

```bash
bash scripts/mvp_freeze_check.sh
cat artifacts/mvp_freeze/summary.json
cat artifacts/mvp_freeze/summary.md
```

Verdict:
- `MVP_FREEZE_PASS`
- `MVP_FREEZE_FAIL` (with `blocking_step`)

## 8. Optional CI (GitHub Actions)

Workflow: `ci` (`workflow_dispatch`)

Use `run_benchmark=true` to trigger optional non-blocking jobs:
- `benchmark-optional`
- `medium-governance-optional`
- `mvp-freeze-optional`
