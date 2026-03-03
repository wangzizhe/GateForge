# GateForge Directory Guide

This file explains what each top-level folder is for, so you can quickly tell:
- what is product code vs generated output,
- what should usually be versioned,
- what to inspect first when debugging.

## Top-Level Folders

| Folder | Purpose | Typical Contents | Should be versioned? |
|---|---|---|---|
| `.git/` | Git internals | commit objects, refs, index | No (managed by Git) |
| `.github/` | CI/CD and repo automation | workflows, actions config | Yes |
| `.venv/` | Local Python virtual environment | installed packages, binaries | No |
| `artifacts/` | Generated run/demo outputs | summaries, manifests, reports | Usually no (ephemeral evidence/output) |
| `assets_private/` | Private model assets and private generated assets | real `.mo` pools, private mutants, source caches | Usually no (private moat assets) |
| `baselines/` | Baseline references for trend/compare modules | previous snapshot/trend inputs | Yes (small curated baselines) |
| `benchmarks/` | Benchmark packs and benchmark inputs | pack JSONs, benchmark case lists | Yes |
| `data/` | Static data/config inputs | source manifests, seed lists | Yes |
| `examples/` | Small public examples and toy/demo models | minimal probes, sample mutants | Yes |
| `gateforge/` | Main product Python modules | pipeline, governance, dataset modules | Yes (core code) |
| `policies/` | Policy profiles and policy configs | gate thresholds, policy templates | Yes |
| `schemas/` | Data schemas/contracts | JSON schema-like contract files | Yes |
| `scripts/` | CLI/demo/run orchestration scripts | `run_*.sh`, `demo_*.sh` | Yes (core operational entrypoints) |
| `skills/` | Skill-related local assets | codex skill helpers | Depends on workflow |
| `tests/` | Test suite | unit/integration/demo tests | Yes |

## Where To Look First

- Product logic: `gateforge/`
- Execution entrypoints: `scripts/`
- Behavioral guarantees: `tests/`
- Policy behavior: `policies/`
- Data/source seed configuration: `data/`

## Moat-Critical Paths (Current Focus)

- Real model pool (private): `assets_private/modelica/open_source`
- Materialized private mutants (if configured): `assets_private/modelica_mutants/`
- Real run outputs and manifests: `artifacts/*real*` and `artifacts/private_model_mutation_*`

## Quick Rule Of Thumb

- If it is **code/config/contract**, it belongs in Git.
- If it is **large generated output/private assets/local env**, keep it out of Git by default.
