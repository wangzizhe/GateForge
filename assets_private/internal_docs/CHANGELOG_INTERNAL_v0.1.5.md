# GateForge Internal Changelog - v0.1.5

Date: 2026-03-22
Base tag: v0.1.4

## Internal Focus
- Stabilize the `v4` LLM replanning lane so it remains release-grade while the Agent core stops depending on provider-specific planner assumptions.
- Keep `v5` as the harder branch-choice lane, but tighten attribution so we can measure branch decision quality and guided-search contribution against a deterministic rule baseline.
- Prepare `v0.1.5` as the release where the multistep Agent core becomes provider-agnostic and the LLM contribution story shifts from "used" to "quality of decisions".

## What Changed (Internal)

### 1) Planner-core decoupling
- Introduced a provider-agnostic multistep planner contract in the live executor so `plan`, `replan`, and budgeted `replan` all flow through one schema.
- Added planner bookkeeping fields throughout the result chain:
  - `planner_contract_version`
  - `planner_family`
  - `planner_adapter`
  - `planner_request_kind`
- Preserved the active LLM provider path while making the core planner state machine less provider-specific.

### 2) `v5` branch-choice hardening
- Tightened `v5` branch-stall and wrong-branch recovery bookkeeping so repeated branch misses surface as explicit `replan` signals.
- Stabilized the carry-over memory from first plan to replan so `previous_branch`, candidate directions, and branch choice reason survive long enough to support deeper branch correction.
- Kept `v5` as a live headroom lane rather than saturating it with new deterministic shortcuts.

### 3) LLM-guided search closed loop
- Promoted guided-search accounting from a loose signal into explicit execution evidence:
  - `llm_guided_search_used`
  - `search_budget_followed`
  - `llm_budget_helped_resolution`
  - `llm_guided_search_resolution`
- Tightened the final payload so guided-search contribution is inferred and persisted when the model reaches a passing state after following the LLM budget.

### 4) Decision-quality accounting
- Extended baseline/evidence summaries with provider-agnostic and decision-quality views:
  - planner backend/provider/family/adapter counts
  - first-plan vs replan branch-match signals
  - branch-miss-after-replan signals
  - guided-search resolution counts
- Tightened the split between:
  - deterministic/template paths
  - first-plan LLM paths
  - replan paths
  - guided-search-assisted paths

### 5) `v0.1.5` release plumbing
- Added `v0.1.5` release evidence checks on top of the `v0.1.4` preflight chain.
- New preflight checks now require:
  - `v4` replanning stability to remain `PASS`
  - `v5` LLM-backed branch-choice to beat the rule baseline while keeping branch errors low
  - `v5` guided-search to show non-zero execution and non-zero resolution contribution
- Updated release entrypoints so the default preflight now targets `v0.1.5`.

## Validation Performed
- Targeted unit tests for:
  - multistep planner contract propagation
  - run-contract live usage field propagation
  - multistep baseline summary accounting
  - multistep evidence accounting
  - release preflight wrappers
- `v5` live validation in two modes:
  - `rule` baseline
  - `llm-backed` authority
- `v0.1.5` release preflight once both authority artifacts were in place.

## Outcome
- `v0.1.5` becomes the release where the internal story shifts from:
  - "an LLM-backed planner can replan on harder multistep tasks"
  to:
  - "the Agent core is provider-agnostic, and the branch-choice plus guided-search contribution of the LLM is measured against a deterministic baseline"

## Next Internal Step
- Decide whether the post-`v0.1.5` main line should prioritize:
  - a harder `v6` realism lane
  - or deeper multi-replan / longer-horizon backtracking on the current `v5` lane
