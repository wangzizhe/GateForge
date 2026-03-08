#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PLAN_PATH="${1:-${GATEFORGE_AGENT_LONGHAUL_PLAN_PATH:-plans/agent_modelica_longhaul_120m_plan_v0.md}}"
if [ ! -f "$PLAN_PATH" ]; then
  echo "Missing plan file: $PLAN_PATH" >&2
  exit 1
fi

set +e
PLAN_EXPORTS="$(
  python3 - "$PLAN_PATH" <<'PY'
import json
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
begin = "<!-- GATEFORGE_LONGHAUL_PLAN_V0_BEGIN -->"
end = "<!-- GATEFORGE_LONGHAUL_PLAN_V0_END -->"

start = text.find(begin)
stop = text.find(end)
if start < 0 or stop < 0 or stop <= start:
    raise SystemExit(f"Plan markers not found in {path}")

payload_text = text[start + len(begin):stop].strip()
payload = json.loads(payload_text)
if not isinstance(payload, dict):
    raise SystemExit("Plan payload must be a JSON object")

schema = str(payload.get("schema_version") or "").strip()
if schema != "agent_modelica_longhaul_plan_v0":
    raise SystemExit(f"Unsupported schema_version: {schema}")

longhaul = payload.get("longhaul") if isinstance(payload.get("longhaul"), dict) else {}
env_rows = payload.get("env") if isinstance(payload.get("env"), dict) else {}
segment_command = str(payload.get("segment_command") or "").strip()
if not segment_command:
    raise SystemExit("segment_command is required")

mapping = {
    "out_dir": "GATEFORGE_AGENT_LONGHAUL_OUT_DIR",
    "total_minutes": "GATEFORGE_AGENT_LONGHAUL_TOTAL_MINUTES",
    "segment_timeout_sec": "GATEFORGE_AGENT_LONGHAUL_SEGMENT_TIMEOUT_SEC",
    "max_segments": "GATEFORGE_AGENT_LONGHAUL_MAX_SEGMENTS",
    "retry_per_segment": "GATEFORGE_AGENT_LONGHAUL_RETRY_PER_SEGMENT",
    "continue_on_fail": "GATEFORGE_AGENT_LONGHAUL_CONTINUE_ON_FAIL",
    "sleep_between_sec": "GATEFORGE_AGENT_LONGHAUL_SLEEP_BETWEEN_SEC",
    "resume": "GATEFORGE_AGENT_LONGHAUL_RESUME",
    "cwd": "GATEFORGE_AGENT_LONGHAUL_CWD",
}

print(f'export GATEFORGE_AGENT_LONGHAUL_PLAN_PATH={shlex.quote(str(path))}')
print(f'export GATEFORGE_AGENT_LONGHAUL_SEGMENT_COMMAND={shlex.quote(segment_command)}')

for key, env_name in mapping.items():
    if key in longhaul and str(longhaul.get(key)).strip():
        print(f"export {env_name}={shlex.quote(str(longhaul.get(key)))}")

for key, value in env_rows.items():
    env_key = str(key).strip()
    if not env_key:
        continue
    print(f"export {env_key}={shlex.quote(str(value))}")
PY
)"
PLAN_RC=$?
set -e

if [ "$PLAN_RC" -ne 0 ]; then
  if [ -n "${PLAN_EXPORTS:-}" ]; then
    echo "$PLAN_EXPORTS" >&2
  fi
  exit "$PLAN_RC"
fi

eval "$PLAN_EXPORTS"

bash scripts/run_agent_modelica_longhaul_v0.sh
