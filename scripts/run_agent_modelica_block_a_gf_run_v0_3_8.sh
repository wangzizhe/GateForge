#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

python3 scripts/block_a_gf_run_v0_3_8.py "$@"
