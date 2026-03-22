# Changelog

All notable changes to this project are documented in this file.

## [v0.1.5] - 2026-03-22
### Added
- Added provider-agnostic multistep planner-contract accounting across plan, replan, and guided-search runs.
- Added `v0.1.5` release preflight checks for `v4` replanning stability and `v5` branch-choice plus guided-search evidence.

### Changed
- Improved `v5` multistep evaluation so branch-choice, replanning, and guided-search evidence are measured against a rule baseline instead of LLM usage alone.
- Improved release-facing evidence so planner family/adapter, branch-match quality, and guided-search contribution are explicitly separated.

### Validation
- `v4` replanning authority remains saturated with non-zero switch-branch replan success.
- `v5` release lane compares Gemini against rule baseline and requires non-zero branch-aware replanning plus guided-search contribution.

## [v0.1.4] - 2026-03-21
### Added
- Added a harder `source-blind multistep` v5 realism lane with branch-sensitive failure exposure.
- Added LLM branch-quality and budgeted-replanning accounting for multistep repair runs.
- Added `v0.1.4` release preflight checks for v4 LLM replanning and v5 branch-decision evidence.

### Changed
- Improved Gemini-guided multistep repair so the planner can replan, switch branch, and allocate budget across branch diagnosis, trap escape, and resolution.
- Improved release-facing evidence so LLM plan, replan, branch-correction, and guided-search contributions are explicitly separated.

### Validation
- `v4` LLM-replan authority target: stabilized to `6/6 PASS` with non-zero switch-branch replan success.
- `v5` authority establishes new headroom while preserving real Gemini contribution signals.

## [v0.1.3] - 2026-03-20
### Added
- Added a source-blind behavioral-robustness evaluation mode.
- Added a source-blind multistep evaluation lane for staged failure exposure and stage-aware control.

### Changed
- Improved autonomous repair behavior on behavioral-robustness tasks without relying on source-model rollback.
- Improved Agent control flow so it can unlock a second failure stage and shift repair focus instead of repeatedly revisiting the first stage.

### Fixed
- Fixed robustness result aggregation and release-facing summary cleanliness.
- Fixed release preflight so `v0.1.3` checks both source-blind robustness evidence and multistep stage-aware evidence.

### Validation
- Source-blind behavioral-robustness baseline: `2/18 PASS`
- Source-blind deterministic repair: `18/18 PASS`
- Source-blind multistep authority baseline: `stage_2_unlock_pct = 83.33`, `stage_1_revisit_after_unlock_count = 0`

## [v0.1.2] - 2026-03-13
### Added
- Added short-latency fast checks for structural and connector repair validation.

### Changed
- Improved end-to-end Modelica repair reliability across the realism validation path.
- Strengthened deterministic repair behavior for structural, connector, and initialization failures.
- Updated release-facing docs and package metadata for `v0.1.2`.

### Fixed
- Fixed realism summary and decision inconsistencies so final reports no longer diverge on the same completed run.
- Fixed release-preflight orchestrator parameter selection that previously crashed on unordered parameter-name sets.
- Fixed remaining failure-classification drift in the realism validation path.

### Validation
- Latest authority realism run: `PASS`, `decision=promote`, `primary_reason=none`.
- `v0.1.2` release preflight: `PASS`.

## [v0.1.1] - 2026-03-07
### Added
- Added strict OpenModelica preflight checks in the problem-plan execution path.
- Added stronger release preflight gates for learning-readiness, private-asset guard, and live smoke validation.

### Changed
- Hardened mutation execution and validation flow for reproducible Modelica repair benchmarking.
- Improved phase-scoped mutation generation and diagnostics in problem-plan execution.
- Improved Docker-based OpenModelica validation stability for local macOS workflows.
- Switched Agent Modelica L4/L5 acceptance to dual-mode evaluation: uplift delta when baseline has headroom, absolute non-regression when baseline is saturated.
- Extended release preflight and CI summaries to expose L5 acceptance mode and non-regression signals.

### Fixed
- Fixed model loading in Docker OMC validation by resolving absolute model paths.
- Fixed namespaced/package model validation behavior for OMC loading.
- Fixed mutation insertion structure to avoid invalid declaration/equation placement.
- Fixed simulate-stage failure classification (division-by-zero and timeout handling) to improve label quality.

### Validation
- Release preflight (v0.1.1): PASS.
- Live smoke with OpenModelica Docker backend: PASS.

## [v0.1.0-mvp] - 2026-02-20
### Added
- Initial MVP for agent-in-the-loop Modelica repair workflows.
- Baseline run-contract and acceptance gating skeleton.
