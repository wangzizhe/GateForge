#!/usr/bin/env bash
# clean_omc_tmp.sh — Remove orphaned OMC simulation artifacts from system tmp.
#
# Covers two artifact sources:
#
#   1. Subdirectory workspaces (gf_live_exec_*, gf_connector_fast_check_*,
#      gf_mutation_valid_*): created by executor / connector / mutation matrix.
#      With the --user Docker fix these are user-owned and auto-cleaned, but
#      old root-owned ones need Docker to delete.
#
#   2. Loose files dumped directly into /tmp root: *.c *.o *_res.mat *.makefile
#      etc. These were written by the pre-fix dataset_mutation_validation_matrix
#      which mounted /tmp itself as the Docker workspace. User-owned; safe to
#      delete with find -delete.
#
# Usage:
#   ./scripts/clean_omc_tmp.sh              # dry-run (show what would be deleted)
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
TMPDIR_PATH="$(python3 -c 'import tempfile; print(tempfile.gettempdir())')"
REPO_TMP_PATH="$(cd "$(dirname "$0")/.." && pwd)/tmp/docker"

echo "==> Scanning: $TMPDIR_PATH"
[ -d "$REPO_TMP_PATH" ] && echo "==> Scanning: $REPO_TMP_PATH"
echo ""

# ── Part 1: workspace subdirectories ────────────────────────────────────────
echo "--- Part 1: workspace subdirectories (gf_live_exec_*, gf_connector_fast_check_*, gf_mutation_valid_*, gf_v0*, repo tmp/docker/*)"

DIR_LIST="$(mktemp)"
# system /tmp
find "$TMPDIR_PATH" -maxdepth 1 -type d \( \
    -name 'gf_live_exec_*' \
    -o -name 'gf_connector_fast_check_*' \
    -o -name 'gf_mutation_valid_*' \
    -o -name 'gf_v0*' \
    -o -name 'v0[0-9]*_*' \
\) 2>/dev/null | sort > "$DIR_LIST"
# repo-local tmp/docker (all subdirs)
if [ -d "$REPO_TMP_PATH" ]; then
    find "$REPO_TMP_PATH" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort >> "$DIR_LIST"
fi

DIR_COUNT="$(wc -l < "$DIR_LIST" | tr -d ' ')"

if [ "$DIR_COUNT" -eq 0 ]; then
    echo "  (none)"
else
    echo "  Found $DIR_COUNT director$([ "$DIR_COUNT" -eq 1 ] && echo y || echo ies):"
    while IFS= read -r t; do
        SIZE="$(du -sh "$t" 2>/dev/null | cut -f1 || echo '?')"
        echo "    $SIZE  $t"
    done < "$DIR_LIST"
fi

# ── Part 2: loose OMC artifact files in /tmp root ───────────────────────────
echo ""
echo "--- Part 2: loose OMC artifacts in /tmp root (*.c *.o *_res.mat *.makefile ...)"

LOOSE_LIST="$(mktemp)"
find "$TMPDIR_PATH" -maxdepth 1 -type f \( \
    -name "*.c" -o -name "*.o" -o -name "*.mat" \
    -o -name "*.makefile" -o -name "*.libs" \
    -o -name "*_init.xml" -o -name "*_info.json" \
    -o -name "run.mos" \
\) 2>/dev/null | sort > "$LOOSE_LIST"

LOOSE_COUNT="$(wc -l < "$LOOSE_LIST" | tr -d ' ')"
if [ "$LOOSE_COUNT" -eq 0 ]; then
    echo "  (none)"
else
    LOOSE_SIZE="$(xargs du -ch 2>/dev/null < "$LOOSE_LIST" | tail -1 | cut -f1 || echo '?')"
    echo "  Found $LOOSE_COUNT files ($LOOSE_SIZE total)"
    head -5 "$LOOSE_LIST" | while IFS= read -r f; do echo "    $f"; done
    [ "$LOOSE_COUNT" -gt 5 ] && echo "    ... and $((LOOSE_COUNT - 5)) more"
fi

echo ""
TOTAL=$((DIR_COUNT + LOOSE_COUNT))
if [ "$TOTAL" -eq 0 ]; then
    rm -f "$DIR_LIST" "$LOOSE_LIST"
    echo "Nothing to clean."
    exit 0
fi

if [ "$FORCE" -eq 0 ]; then
    rm -f "$DIR_LIST" "$LOOSE_LIST"
    echo "Dry-run mode. Pass --force to delete."
    exit 0
fi

echo "==> Deleting..."

# Delete subdirectories (user-owned first, Docker fallback for root-owned)
FAILED_LIST="$(mktemp)"
while IFS= read -r t; do
    if [ -z "$t" ]; then continue; fi
    if rm -rf "$t" 2>/dev/null && [ ! -e "$t" ]; then
        echo "  removed (user-owned): $t"
    else
        echo "$t" >> "$FAILED_LIST"
    fi
done < "$DIR_LIST"
rm -f "$DIR_LIST"

FAILED_COUNT="$(wc -l < "$FAILED_LIST" | tr -d ' ')"
if [ "$FAILED_COUNT" -gt 0 ]; then
    echo ""
    echo "  $FAILED_COUNT directories need Docker (root-owned):"
    if ! command -v docker &>/dev/null; then
        rm -f "$FAILED_LIST"
        echo "  ERROR: docker not found. Run: sudo rm -rf <path>" >&2
        exit 1
    fi
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        BASENAME="$(basename "$t")"
        PARENT="$(dirname "$t")"
        docker run --rm -v "${PARENT}:/host_tmp" "$DOCKER_IMAGE" rm -rf "/host_tmp/${BASENAME}"
        echo "  removed (docker): $t"
    done < "$FAILED_LIST"
fi
rm -f "$FAILED_LIST"

# Delete loose OMC artifact files (always user-owned)
if [ "$LOOSE_COUNT" -gt 0 ]; then
    xargs rm -f 2>/dev/null < "$LOOSE_LIST" && echo "  removed $LOOSE_COUNT loose artifact files"
fi
rm -f "$LOOSE_LIST"

echo ""
echo "Done."
