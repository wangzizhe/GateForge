#!/usr/bin/env bash
set -euo pipefail

PATTERN="${1:-test_*.py}"
SHARD_TIMEOUT="${SHARD_TIMEOUT:-25m}"
LOG_DIR="${CI_LOG_DIR:-artifacts/ci_logs}"
mkdir -p "$LOG_DIR"

safe_pattern="$(printf '%s' "$PATTERN" | tr -c 'A-Za-z0-9._-' '_')"
LOG_FILE="$LOG_DIR/unittest_${safe_pattern}.log"

TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then
  TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then
  TIMEOUT_BIN="gtimeout"
fi

PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

set +e
if [ -n "$TIMEOUT_BIN" ]; then
  ("$TIMEOUT_BIN" "$SHARD_TIMEOUT" "$PYTHON_BIN" -X faulthandler -m unittest discover -s tests -p "$PATTERN" -v) \
    >"$LOG_FILE" 2>&1
else
  echo "[ci] warning: timeout command not found; running shard without enforced timeout" >"$LOG_FILE"
  ("$PYTHON_BIN" -X faulthandler -m unittest discover -s tests -p "$PATTERN" -v) >>"$LOG_FILE" 2>&1
fi
rc=$?
set -e

cat "$LOG_FILE"

if [ "$rc" -eq 0 ]; then
  exit 0
fi

echo ""
echo "[ci] shard failed: pattern=$PATTERN exit_code=$rc"

last_test_line="$(grep -E '^test_.*\.\.\.$' "$LOG_FILE" | tail -n 1 || true)"
if [ -n "$last_test_line" ]; then
  echo "[ci] last running test before failure: $last_test_line"
fi

if [ "$rc" -eq 124 ]; then
  echo "[ci] shard timed out after $SHARD_TIMEOUT"
fi

echo "[ci] tail of shard log ($LOG_FILE):"
tail -n 80 "$LOG_FILE" || true

exit "$rc"
