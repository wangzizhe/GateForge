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

## Agentic Modelica Workflow Benchmark

Benchmark snapshot as of May 20, 2026.

Both agents use the same foundation model and are evaluated under the same benchmark and wall-clock conditions.

GateForge outperforms OpenCode by +10 solved tasks overall, with gains concentrated in medium and hard Modelica workflows.

| Agent | Total | easy | medium | hard |
| --- | ---: | ---: | ---: | ---: |
| GateForge | 130/132 | 21/21 | 56/56 | 53/55 |
| OpenCode | 120/132 | 21/21 | 50/56 | 42/55 |

GateForge used about 40% fewer tokens and finished about 30% faster.

| Agent | tokens | wall time |
| --- | ---: | ---: |
| GateForge | ~39.7M | ~14,658s |
| OpenCode | ~66.1M | ~20,843s |

Comparisons with additional AI agents, such as Codex and Claude Code, will follow.

## Legal Notice

Without prior written permission, no content on this site may be used for AI model training, fine-tuning, evaluation, or dataset construction.

- `LEGAL_NOTICE.md`
- `CONTENT_AUTHORIZATION_POLICY.md`
- `robots.txt`
