# Changelog

All notable changes to this project are documented in this file.

## [v0.1.1] - 2026-03-07
### Added
- Added strict OpenModelica preflight checks in the problem-plan execution path.
- Added stronger release preflight gates for learning-readiness, private-asset guard, and live smoke validation.

### Changed
- Hardened mutation execution and validation flow for reproducible Modelica repair benchmarking.
- Improved phase-scoped mutation generation and diagnostics in problem-plan execution.
- Improved Docker-based OpenModelica validation stability for local macOS workflows.

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
