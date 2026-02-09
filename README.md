# GateForge (minimal skeleton)

Minimal `run -> evidence -> gate` pipeline for learning and bootstrapping CI/regression governance.

## Step 1: Install and run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
python -m gateforge.smoke --backend mock --out artifacts/evidence.json
cat artifacts/evidence.json
```

## Step 2: What this minimal CI does

- Runs tests on each push/PR.
- Runs a smoke pipeline that produces `artifacts/evidence.json`.
- Uploads the evidence artifact in GitHub Actions.

This is intentionally small. It proves your governance layer can always produce machine-readable evidence before adding real simulation complexity.

## Step 3: OpenModelica mode (probe for now)

```bash
python -m gateforge.smoke --backend openmodelica --out artifacts/evidence-om.json
```

Current behavior:
- If `omc` is available and returns version: `PASS`.
- If `omc` is missing: `NEEDS_REVIEW`.

Next step is to replace the probe with real compile/simulate execution.
