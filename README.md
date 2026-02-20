# GateForge

GateForge is a Python toolkit for simulation governance and regression gating with reproducible evidence.

For each change, it helps answer:
- Did behavior regress versus baseline?
- Should this be `PASS`, `FAIL`, or `NEEDS_REVIEW`?
- What evidence supports the decision?

## Requirements

- Python `>=3.10`
- Optional: Docker Desktop (for OpenModelica flows)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

## Quick Start

Validate a proposal:

```bash
python3 -m gateforge.proposal_validate --in examples/proposals/proposal_v0.json
```

Run end-to-end with automatic baseline resolution:

```bash
python3 -m gateforge.run \
  --proposal examples/proposals/proposal_v0.json \
  --baseline auto \
  --out artifacts/proposal_run.json
```

Inspect outputs:

```bash
cat artifacts/proposal_run.json
cat artifacts/proposal_run.md
cat artifacts/regression_from_proposal.json
```

## Common Commands

- `bash scripts/demo_all.sh` (run bundled demos)
- `bash scripts/demo_ci_matrix.sh` (fast local validation matrix)
- `POLICY_PROFILE=industrial_strict_v0 bash scripts/demo_all.sh` (stricter policy)

Use `python3 -m gateforge.<module> --help` for module options.

## Docs

- `DEMO.md`: demo catalog and expected results
- `OPERATIONS.md`: triage and release workflows
- `LICENSE`

failure-path test
