#!/usr/bin/env bash
set -euo pipefail

PATTERNS_CSV="${1:-test_*.py}"
SHARD_TIMEOUT="${SHARD_TIMEOUT:-25m}"
LOG_DIR="${CI_LOG_DIR:-artifacts/ci_logs}"
mkdir -p "$LOG_DIR"

safe_patterns="$(printf '%s' "$PATTERNS_CSV" | tr -c 'A-Za-z0-9._,-' '_')"
LOG_FILE="$LOG_DIR/unittest_${safe_patterns}.log"

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
IFS=',' read -r -a PATTERNS <<< "$PATTERNS_CSV"

echo "" >"$LOG_FILE"

total_start="$(date +%s)"
total_files=0
rc=0
failed_pattern=""

for PATTERN in "${PATTERNS[@]}"; do
  pattern_file_count="$(find tests -maxdepth 1 -type f -name "$PATTERN" | wc -l | tr -d ' ')"
  total_files=$((total_files + pattern_file_count))
  echo "[ci] running pattern=$PATTERN test_files=$pattern_file_count timeout=$SHARD_TIMEOUT" | tee -a "$LOG_FILE"
  pattern_start="$(date +%s)"
  if [ -n "$TIMEOUT_BIN" ]; then
    ("$TIMEOUT_BIN" "$SHARD_TIMEOUT" "$PYTHON_BIN" -X faulthandler -m unittest discover -s tests -p "$PATTERN" -v) \
      >>"$LOG_FILE" 2>&1
  else
    echo "[ci] warning: timeout command not found; running shard without enforced timeout" | tee -a "$LOG_FILE"
    ("$PYTHON_BIN" -X faulthandler -m unittest discover -s tests -p "$PATTERN" -v) >>"$LOG_FILE" 2>&1
  fi
  pattern_rc=$?
  pattern_elapsed=$(( $(date +%s) - pattern_start ))
  echo "[ci] completed pattern=$PATTERN exit_code=$pattern_rc elapsed_s=$pattern_elapsed" | tee -a "$LOG_FILE"
  if [ "$pattern_rc" -ne 0 ]; then
    rc="$pattern_rc"
    failed_pattern="$PATTERN"
    break
  fi
done
set -e

cat "$LOG_FILE"
total_elapsed=$(( $(date +%s) - total_start ))

summary_line="[ci] shard summary patterns=$PATTERNS_CSV test_files=$total_files elapsed_s=$total_elapsed exit_code=$rc"
echo "$summary_line"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### Unittest shard summary"
    echo ""
    echo "- patterns: \`$PATTERNS_CSV\`"
    echo "- test_files: \`$total_files\`"
    echo "- elapsed_s: \`$total_elapsed\`"
    echo "- exit_code: \`$rc\`"
    echo ""
  } >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$rc" -eq 0 ]; then
  exit 0
fi

echo ""
echo "[ci] shard failed: pattern=$failed_pattern exit_code=$rc"

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
