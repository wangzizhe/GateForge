#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MVP_FREEZE_TEST_MODE=targeted bash scripts/mvp_freeze_check.sh
