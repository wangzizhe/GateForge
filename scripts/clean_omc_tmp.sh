#!/usr/bin/env bash
# clean_omc_tmp.sh — Remove orphaned OMC workspace directories from system tmp.
#
# Why this exists:
#   GateForge runs OMC inside Docker, which writes files as root into the
#   mounted host temp directory (gf_live_exec_* / gf_connector_fast_check_*).
#   shutil.rmtree(ignore_errors=True) silently fails on root-owned files,
#   leaving orphaned directories that accumulate on disk.
#
# Strategy:
#   1. Try plain rm -rf first (works for user-owned dirs).
#   2. For any that remain, run a Docker alpine container to delete them
#      (the container runs as root, so it can delete root-owned files).
#
# Usage:
#   ./scripts/clean_omc_tmp.sh              # dry-run by default
#   ./scripts/clean_omc_tmp.sh --force      # actually delete
#   DOCKER_IMAGE=alpine:3.20 ./scripts/clean_omc_tmp.sh --force
#
# Exit codes: 0 = success (including "nothing to clean"), 1 = error.

set -euo pipefail

FORCE=0
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --help|-h)
            sed -n '2,/^set /p' "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 1
            ;;
    esac
done

DOCKER_IMAGE="${DOCKER_IMAGE:-alpine:3.20}"

# Locate system tmp directory (macOS uses /private/var/folders/.../T/).
# python3 is the most portable way to find it.
TMPDIR_PATH="$(python3 -c 'import tempfile; print(tempfile.gettempdir())')"

echo "==> Scanning: $TMPDIR_PATH"
echo "==> Prefixes: gf_live_exec_*  gf_connector_fast_check_*"
echo ""

# Collect matching directories into a temp file (bash 3.2 compatible — no mapfile).
TMP_LIST="$(mktemp)"
find "$TMPDIR_PATH" -maxdepth 1 -type d \( -name 'gf_live_exec_*' -o -name 'gf_connector_fast_check_*' \) 2>/dev/null | sort > "$TMP_LIST"

COUNT="$(wc -l < "$TMP_LIST" | tr -d ' ')"

if [ "$COUNT" -eq 0 ]; then
    rm -f "$TMP_LIST"
    echo "Nothing to clean."
    exit 0
fi

echo "Found $COUNT director$([ "$COUNT" -eq 1 ] && echo y || echo ies):"
while IFS= read -r t; do
    SIZE="$(du -sh "$t" 2>/dev/null | cut -f1 || echo '?')"
    echo "  $SIZE  $t"
done < "$TMP_LIST"
echo ""

if [ "$FORCE" -eq 0 ]; then
    rm -f "$TMP_LIST"
    echo "Dry-run mode. Pass --force to delete."
    exit 0
fi

echo "==> Deleting..."
FAILED_LIST="$(mktemp)"

while IFS= read -r t; do
    if rm -rf "$t" 2>/dev/null; then
        echo "  removed (user-owned): $t"
    else
        echo "$t" >> "$FAILED_LIST"
    fi
done < "$TMP_LIST"
rm -f "$TMP_LIST"

FAILED_COUNT="$(wc -l < "$FAILED_LIST" | tr -d ' ')"

if [ "$FAILED_COUNT" -gt 0 ]; then
    echo ""
    echo "==> $FAILED_COUNT director$([ "$FAILED_COUNT" -eq 1 ] && echo y || echo ies) require Docker (root-owned files):"
    while IFS= read -r t; do
        echo "  $t"
    done < "$FAILED_LIST"

    if ! command -v docker &>/dev/null; then
        rm -f "$FAILED_LIST"
        echo ""
        echo "ERROR: docker not found. Cannot remove root-owned directories." >&2
        echo "Run manually: sudo rm -rf <path>" >&2
        exit 1
    fi

    while IFS= read -r t; do
        BASENAME="$(basename "$t")"
        PARENT="$(dirname "$t")"
        echo "  docker-removing: $t"
        docker run --rm \
            -v "${PARENT}:/host_tmp" \
            "$DOCKER_IMAGE" \
            rm -rf "/host_tmp/${BASENAME}"
        echo "  removed (docker): $t"
    done < "$FAILED_LIST"
fi

rm -f "$FAILED_LIST"
echo ""
echo "Done."
