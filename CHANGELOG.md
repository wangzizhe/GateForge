# Changelog

All notable public changes to this project are documented in this file. Detailed experiment results, failure attribution, and internal analysis notes are tracked in private documentation and are intentionally not published here.

## [v0.19.66] - 2026-04-24

### Added
- Added public infrastructure for Modelica generation audits, failure attribution, repair-budget analysis, prompt/profile comparison, and benchmark synthesis.
- Added CI-safe fallback behavior so public tests do not depend on private assets or local experiment artifacts.
- Added public runners and tests for the latest internal evaluation workflows.

### Changed
- Closed the v0.19.x public phase with sanitized release notes.
- Kept detailed experiment metrics, failure taxonomies, private task pools, and internal conclusions in private documentation.
- Preserved the executor boundary: new evaluation utilities do not add deterministic repair, routing, or hidden hint logic to the core repair loop.

### Validation
- Local Core A shard passed with the repository CI shard runner.
- v0.19.x public tests for the newly added audit and synthesis utilities pass under `python3 -m unittest`.
- Public release note intentionally reports capabilities at a high level only; detailed experimental results remain internal.

## [v0.18.2] - 2026-04-14

### Added
- Added public infrastructure for the v0.4.0-v0.18.2 experimental phase, including governance, evaluation, benchmark, execution, and workflow-to-product assessment utilities.
- Added tests and public code paths for the phase-level infrastructure that remains useful outside the private experiment record.

### Changed
- Consolidated the internal v0.4.0-v0.18.2 experiment chain into this public phase closeout.
- Removed detailed per-version experiment metrics, intermediate conclusions, private decision labels, and artifact deep links from the public changelog.
- Kept detailed phase evidence and interpretation in private internal documentation.

### Validation
- Public validation is summarized at the phase level only.
- Detailed run counts, pass rates, failure buckets, and artifact-level conclusions are intentionally not published.

## [v0.3.34] - 2026-04-05

### Added
- Added early public infrastructure for Modelica agent evaluation, OpenModelica integration, benchmark construction, repair-loop execution, and external-agent comparison scaffolding.
- Added tests and runnable utilities for the early experimental line where they remain part of the public codebase.

### Changed
- Consolidated the internal v0.3.x experiment chain into this public phase closeout.
- Removed task-level metrics, lane-by-lane conclusions, artifact deep links, private benchmark routing, and detailed attribution traces from the public changelog.
- Kept the public record focused on capability areas rather than experimental play-by-play.

### Validation
- Public validation is summarized at the phase level only.
- Detailed task counts, pass rates, branch/lane outcomes, and intermediate research conclusions are intentionally not published.

## [v0.2.0] - 2026-03-26

### Added
- Added the public rule-engine, experience, replay, planner-context, cross-domain validation, and difficulty-layer infrastructure for the early Modelica repair evaluation line.
- Added benchmark fixture preparation, source-viability filtering, diagnostic subtype metadata, and reusable evaluation utilities.

### Changed
- Consolidated the internal v0.2.x experiment chain into this public phase entry.
- Kept the public record focused on reusable engineering surfaces rather than benchmark-by-benchmark results.
- Removed detailed comparison deltas, case counts, track-level outcomes, artifact deep links, and attribution traces from the public changelog.

### Validation
- Public validation is summarized at the phase level only.
- Detailed benchmark metrics, pass rates, per-track conclusions, and internal experiment artifacts are intentionally not published.

## [v0.1.9] - 2026-03-25

### Added
- Added the first public Agent Modelica repair foundation: OpenModelica validation, deterministic repair scaffolding, source-blind and multistep evaluation surfaces, guided-search modules, planner/replan modules, workspace isolation, and baseline/generalization benchmark utilities.
- Added modularization work that split large executor responsibilities into separately testable components.

### Changed
- Consolidated the internal v0.1.1-v0.1.9 experiment and hardening chain into this public phase entry.
- Kept the public record focused on engineering maturity, module extraction, and validation surfaces rather than detailed experimental outcomes.
- Removed concrete pass counts, line-count deltas, benchmark thresholds, task-level outcomes, and internal attribution details from the public changelog.

### Validation
- Public validation is summarized at the phase level only.
- Detailed smoke results, preflight metrics, benchmark rates, and intermediate experiment conclusions are intentionally not published.

## [v0.1.0-mvp] - 2026-02-20

### Added
- Initial MVP for agent-in-the-loop Modelica repair workflows.
- Added the first governance loop for proposal-driven execution, evidence collection, regression gating, policy decisions, and human-readable reporting.

### Validation
- MVP validation and iteration release.
