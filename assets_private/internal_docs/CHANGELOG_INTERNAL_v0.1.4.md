# GateForge Internal Changelog - v0.1.4

Date: 2026-03-21
Base tag: v0.1.3

## Internal Focus
- Move beyond “an LLM was called” and make branch choice, replanning, and budget allocation first-class capability signals for the LLM-backed planner.
- Stabilize the existing `v4 llm-forcing` line so LLM replanning is publishable, then create a harder `v5` line with fresh headroom.
- Prepare `v0.1.4` as the first release where the LLM-backed planner is a measurable branch-decision agent on `source-blind multistep`.

## What Changed (Internal)

### 1) `v4 llm-replan` hardening
- Tightened `previous_plan_failed_signal` handling so `llm_replan` triggers on real stalls, branch miss, or trap escape failure instead of noise.
- Tightened budget handling for:
  - `continue_current_branch`
  - `switch_branch`
  - post-replan resolution
- Stabilized the bookkeeping around:
  - `llm_replan_used_count`
  - `llm_replan_resolution_count`
  - `llm_replan_switch_branch_count`
  - `llm_replan_switch_branch_success_count`
  - `llm_replan_budget_efficiency`

### 2) `v5 multistep realism`
- Added `realism_version = v5` on top of the existing `source-blind multistep` lane instead of replacing `v4`.
- Introduced harder multistep variants with:
  - two-parameter-cluster coupling
  - stronger `stage_2` branching
  - trap directions closer to local optima
  - cases where one replan is not always enough
- Added task metadata so the runtime can distinguish `v4 llm-forcing` from `v5` harder realism tasks.

### 3) Branch-choice quality accounting
- Extended run records, baseline summaries, and evidence summaries with explicit branch-quality fields:
  - `first_plan_branch_match`
  - `replan_branch_match`
  - `wrong_branch_enter_count`
  - `wrong_branch_recovery_count`
  - `trap_escape_success`
  - `median_round_to_correct_branch`
- Extended LLM accounting so we can now separate:
  - deterministic
  - first-plan
  - replan
  - switch-branch replan
  - second-replan contributions

### 4) LLM-guided search budget allocation
- Promoted `replan_budget_*` from passive record fields into execution control.
- Added `llm_guided_search_*` signals so we can tell when the search path actually followed the LLM budget.
- Added support for deeper `v5` branch-aware replanning and, when needed, a second replan.

### 5) Release preflight for `v0.1.4`
- Added `v0.1.4` release evidence checks on top of the existing release preflight chain.
- New release preflight now checks:
  - `v4` LLM-replan authority status
  - `v5` branch-choice authority status
- Updated release entrypoints and README so the default preflight now targets `v0.1.4`.

## Validation Performed
- Targeted unit tests for:
  - multistep taskset generation
  - live executor LLM plan/replan handling
  - run-contract field propagation
  - baseline/evidence summaries
  - release preflight wrappers
- `v4` authority validation to confirm:
  - `6/6 PASS`
  - non-zero `llm_replan_used_count`
  - non-zero switch-branch replan success
  - `branch_selection_error_count = 0`
- `v5` smoke and authority validation to confirm:
  - new branch headroom exists
  - LLM planner branch-choice / replan metrics are non-zero
  - the lane is not just another deterministic saturation path

## Outcome
- `v0.1.4` becomes the release where the internal story shifts from:
  - “an LLM-backed planner was forced to participate”
  to:
  - “the LLM-backed planner can make branch decisions, replan after failure, and guide budgeted search on harder multistep tasks”

## Next Internal Step
- If `v5` still leaves clean headroom after release:
  - decide between deeper multi-replan depth
  - or an even harder `v6` line with longer backtracking chains
