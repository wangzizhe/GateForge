#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m gateforge.smoke --backend mock --out baselines/mock_baseline.json --report baselines/mock_baseline.md
echo "Updated baselines/mock_baseline.json and baselines/mock_baseline.md"

