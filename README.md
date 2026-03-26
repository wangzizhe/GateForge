# GateForge

<p align="center">
  <a href="https://github.com/wangzizhe/GateForge/actions/workflows/ci.yml" style="text-decoration:none;"><img src="https://github.com/wangzizhe/GateForge/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>&nbsp;
  <a href="https://github.com/wangzizhe/GateForge/releases" style="text-decoration:none;"><img src="https://img.shields.io/github/release/wangzizhe/GateForge.svg?include_prereleases" alt="Release" /></a>&nbsp;
  <a href="LICENSE" style="text-decoration:none;"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" /></a>&nbsp;
  <a href="https://www.python.org/" style="text-decoration:none;"><img src="https://img.shields.io/badge/python-%3E%3D3.10-3776AB.svg" alt="Python >= 3.10" /></a>
</p>
<p align="center" style="margin: 0.75rem auto 1rem; max-width: 920px; padding: 0.75rem 1rem; border: 1px solid #d0d7de; border-radius: 8px; background: #f6f8fa;">
  <strong>AI Agents for Physical Systems Modeling</strong>
</p>

## Quickstart

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Run targeted tests

```bash
python -m unittest \
  tests.test_agent_modelica_live_executor_gemini_v1 \
  tests.test_agent_modelica_rule_engine_v1 \
  -v
```

### 3. Run the live executor

```bash
python -m gateforge.agent_modelica_live_executor_gemini_v1 \
  --task-id demo \
  --failure-type model_check_error \
  --expected-stage check \
  --mutated-model-path path/to/mutated.mo \
  --source-model-path path/to/source.mo \
  --planner-backend rule \
  --out artifacts/demo_live_executor.json
```

### 4. Run a benchmark track

```bash
python -m gateforge.agent_modelica_gf_hardpack_runner_v1 \
  --pack assets_private/agent_modelica_track_a_valid32_fixture_v1/hardpack_frozen.json \
  --planner-backend gemini \
  --out artifacts/benchmark_track_a/gf_results.json

python -m gateforge.agent_modelica_generalization_benchmark_v1 \
  --pack assets_private/agent_modelica_track_a_valid32_fixture_v1/hardpack_frozen.json \
  --gateforge-results artifacts/benchmark_track_a/gf_results.json \
  --out artifacts/benchmark_track_a/comparison_results.json
```

## Legal Notice

Without prior written permission, no content on this site may be used for AI model training, fine-tuning, evaluation, or dataset construction.

- `LEGAL_NOTICE.md`
- `CONTENT_AUTHORIZATION_POLICY.md`
- `robots.txt`
