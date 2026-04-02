#!/usr/bin/env bash
# install_omc_cleanup_agent.sh — Install a macOS LaunchAgent that runs
# clean_omc_tmp.sh daily at 02:07 to remove orphaned OMC workspace directories.
#
# Usage:
#   ./scripts/install_omc_cleanup_agent.sh          # install
#   ./scripts/install_omc_cleanup_agent.sh --remove  # uninstall
#
# After the Docker --user fix (agent_modelica_live_executor_v1.py),
# new workspace files are user-owned and cleaned up automatically. This agent
# acts as a safety net for any pre-fix orphaned directories.

set -euo pipefail

PLIST_LABEL="com.gateforge.clean-omc-tmp"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="${REPO_ROOT}/scripts/clean_omc_tmp.sh"
LOG_PATH="/tmp/gateforge-clean-omc.log"

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: clean_omc_tmp.sh not found at: $SCRIPT_PATH" >&2
    exit 1
fi

if [ "${1:-}" = "--remove" ]; then
    if launchctl list "$PLIST_LABEL" &>/dev/null; then
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        echo "Unloaded: $PLIST_LABEL"
    fi
    rm -f "$PLIST_PATH"
    echo "Removed: $PLIST_PATH"
    exit 0
fi

mkdir -p "${HOME}/Library/LaunchAgents"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_PATH}</string>
        <string>--force</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>7</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_PATH}</string>
</dict>
</plist>
PLIST

# Reload if already running.
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Installed: $PLIST_LABEL"
echo "Schedule:  daily at 02:07"
echo "Script:    $SCRIPT_PATH"
echo "Log:       $LOG_PATH"
echo ""
echo "To uninstall: ./scripts/install_omc_cleanup_agent.sh --remove"
