# Agent Modelica Acceptance Note (2026W10)

This note fixes the acceptance contract used for the current Agent Modelica release candidate and records the evidence paths that justify promotion.

## Scope

- Domain: Electrical `small+medium`
- Canonical challenge pack: `assets_private/agent_modelica_l4_challenge_pack_v0/taskset_frozen.json`
- Acceptance date: March 10, 2026

## Baseline Contract

The canonical baseline is fixed as:

- `planner_backend = gemini`
- `LLM_MODEL = gemini-3.1-pro-preview`
- `backend = openmodelica_docker`
- `docker_image = openmodelica/openmodelica:v1.26.1-minimal`
- `max_rounds = 2`
- `max_time_sec = 90`

Canonical baseline evidence:

- `artifacts/agent_modelica_l4_canonical_baseline_v0_acceptance_2026W10_headroom_rerun01/summary.json`

Canonical baseline result:

- `decision = hold`
- `primary_reason = baseline_saturated_no_headroom`
- `baseline_off_success_at_k_pct = 100.0`

Interpretation:

- The baseline meets the minimum quality floor.
- The baseline does not leave enough mathematical headroom to require `delta Success@K >= 5pp`.
- L4/L5 acceptance therefore switches from raw uplift mode to absolute non-regression mode.

## L4/L5 Acceptance Contract

Two acceptance modes are now valid:

1. `delta_uplift`
   - Use when baseline meets minimum quality and still has headroom.
   - Promote requires the configured uplift delta.
2. `absolute_non_regression`
   - Use when baseline meets minimum quality but is saturated.
   - Promote requires:
     - `main_success_at_k_pct >= 85.0`
     - `non_regression_ok = true`
     - no quality regression
     - no infra failure

For the current Electrical acceptance, the active mode is:

- `acceptance_mode = absolute_non_regression`

## Electrical Acceptance Result

Electrical uplift evidence:

- `artifacts/agent_modelica_l4_uplift_evidence_v0_acceptance_2026W10_absolute01/decision_summary.json`
- `artifacts/agent_modelica_l4_uplift_evidence_v0_acceptance_2026W10_absolute01/summary.json`
- `artifacts/agent_modelica_l4_uplift_evidence_v0_acceptance_2026W10_absolute01/main_l5/l5_eval_summary.json`
- `artifacts/agent_modelica_l4_uplift_evidence_v0_acceptance_2026W10_absolute01/night_l5/l5_eval_summary.json`

Decision:

- `decision = promote`
- `primary_reason = none`
- `acceptance_mode = absolute_non_regression`

Key metrics:

- `main_success_at_k_pct = 100.0`
- `absolute_success_target_pct = 85.0`
- `non_regression_ok = true`
- `infra_failure_count_total = 0`
- `main_l5.status = PASS`
- `night_l5.status = PASS`

## Release Preflight Result

Release preflight evidence:

- `artifacts/release_v0_1_1_real_2026W10/release_preflight_summary.json`

Result:

- `status = PASS`
- `live_smoke_status = PASS`
- `l3_diagnostic_gate_status = PASS`
- `l5_gate_status = PASS`
- `l5_primary_reason = none`
- `l5_infra_failure_count = 0`

Observed mode in this preflight run:

- `l5_acceptance_mode = delta_uplift`
- `l5_delta_success_at_k_pp = 0.0`

This does not conflict with the Electrical acceptance result.

Reason:

- Release preflight validates the release gate path, live smoke path, and L3/L5 gate plumbing on its configured preflight taskset.
- Electrical acceptance validates the fixed Electrical challenge pack and its current saturated-baseline contract.
- These two runs answer different questions and do not need to share the same acceptance mode.

## Release Decision

Current release conclusion:

- Electrical acceptance: `promote`
- Release preflight: `PASS`
- Release blocker from current evidence: none

This release candidate is acceptable under the current Agent Modelica dual-mode acceptance contract.
