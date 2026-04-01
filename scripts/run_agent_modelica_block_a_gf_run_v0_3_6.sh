#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/block_a_gf_run_v0_3_6.py "$@"
