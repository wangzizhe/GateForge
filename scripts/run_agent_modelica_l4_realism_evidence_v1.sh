#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
CURRENT_BUILDER_SOURCE_PATH="$ROOT_DIR/gateforge/agent_modelica_electrical_mutant_taskset_v0.py"

OUT_DIR="${GATEFORGE_AGENT_L4_REALISM_EVIDENCE_OUT_DIR:-artifacts/agent_modelica_l4_realism_evidence_v1}"
BASE_TASKSET="${GATEFORGE_AGENT_L4_REALISM_BASE_TASKSET:-artifacts/agent_modelica_electrical_realism_frozen_taskset_v1/taskset_frozen.json}"
SCALES="${GATEFORGE_AGENT_L4_REALISM_SCALES:-small,medium}"
REALISM_MODE="${GATEFORGE_AGENT_L4_REALISM_MODE:-lean}"
FAILURE_TYPES="${GATEFORGE_AGENT_L4_REALISM_FAILURE_TYPES:-underconstrained_system,connector_mismatch,initialization_infeasible}"
REQUIRED_CATEGORIES="${GATEFORGE_AGENT_L4_REALISM_REQUIRED_CATEGORIES:-topology_wiring,initialization}"
PER_FAILURE_TYPE_CAP="${GATEFORGE_AGENT_L4_REALISM_PER_FAILURE_TYPE_CAP:-6}"
HOLDOUT_RATIO="${GATEFORGE_AGENT_L4_REALISM_HOLDOUT_RATIO:-0.15}"
SPLIT_SEED="${GATEFORGE_AGENT_L4_REALISM_SPLIT_SEED:-agent_modelica_l4_realism_v1}"
PACK_ID="${GATEFORGE_AGENT_L4_REALISM_PACK_ID:-agent_modelica_realism_pack_v1}"
PACK_VERSION="${GATEFORGE_AGENT_L4_REALISM_PACK_VERSION:-v1}"
PACK_TRACK="${GATEFORGE_AGENT_L4_REALISM_PACK_TRACK:-realism}"
ACCEPTANCE_SCOPE="${GATEFORGE_AGENT_L4_REALISM_ACCEPTANCE_SCOPE:-independent_validation}"
CONTINUE_ON_WEAK_BASELINE="${GATEFORGE_AGENT_L4_REALISM_CONTINUE_ON_WEAK_BASELINE:-1}"
RUN_ID="${GATEFORGE_AGENT_L4_REALISM_RUN_ID:-$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("realism_%Y%m%dT%H%M%SZ"))
PY
)}"
RUN_ROOT_DEFAULT="$OUT_DIR/runs/$RUN_ID"
RUN_ROOT="${GATEFORGE_AGENT_L4_REALISM_RUN_ROOT:-$RUN_ROOT_DEFAULT}"
UPDATE_LATEST="${GATEFORGE_AGENT_L4_REALISM_UPDATE_LATEST:-1}"

BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_BACKEND:-openmodelica_docker}"
CHALLENGE_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_PLANNER_BACKEND:-gemini}"
MAIN_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_PLANNER_BACKEND:-rule}"
NIGHT_PLANNER_BACKEND="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_PLANNER_BACKEND:-gemini}"
CHALLENGE_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LIVE_EXECUTOR_CMD:-}"
MAIN_SWEEP_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_SWEEP_LIVE_EXECUTOR_CMD:-}"
NIGHT_SWEEP_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_SWEEP_LIVE_EXECUTOR_CMD:-}"
MAIN_L5_L3_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L3_LIVE_EXECUTOR_CMD:-}"
MAIN_L5_L4_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_MAIN_L5_L4_LIVE_EXECUTOR_CMD:-}"
NIGHT_L5_L3_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L3_LIVE_EXECUTOR_CMD:-}"
NIGHT_L5_L4_EXECUTOR_CMD="${GATEFORGE_AGENT_L4_UPLIFT_NIGHT_L5_L4_LIVE_EXECUTOR_CMD:-}"

if [ "$REALISM_MODE" = "lean" ]; then
  NIGHT_ENABLED="${GATEFORGE_AGENT_L4_REALISM_NIGHT_ENABLED:-0}"
  PROFILES="${GATEFORGE_AGENT_L4_UPLIFT_PROFILES:-score_v1}"
else
  NIGHT_ENABLED="${GATEFORGE_AGENT_L4_REALISM_NIGHT_ENABLED:-1}"
  PROFILES="${GATEFORGE_AGENT_L4_UPLIFT_PROFILES:-score_v1,score_v1a,score_v1b,score_v1c}"
fi
LIVE_LEDGER_PATH="${GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH:-$RUN_ROOT/private/live_request_ledger.json}"
LIVE_MAX_REQUESTS_PER_RUN="${GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN:-80}"
LIVE_MAX_CONSECUTIVE_429="${GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429:-3}"
LIVE_BACKOFF_BASE_SEC="${GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC:-5}"
LIVE_BACKOFF_MAX_SEC="${GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC:-60}"

if [ ! -f "$BASE_TASKSET" ]; then
  echo "Missing realism base taskset: $BASE_TASKSET" >&2
  exit 1
fi

mkdir -p "$OUT_DIR" "$OUT_DIR/runs"
LOCK_PATH="$OUT_DIR/.active_run_lock.json"

bootstrap_env_exports() {
  python3 - <<'PY'
import json
import os
from gateforge.agent_modelica_live_executor_gemini_v1 import _bootstrap_env_from_repo

keys = [
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "LLM_MODEL",
    "GATEFORGE_GEMINI_MODEL",
    "GEMINI_MODEL",
]
before = {key: str(os.environ.get(key) or "") for key in keys}
_bootstrap_env_from_repo(allowed_keys=set(keys))
after = {key: str(os.environ.get(key) or "") for key in keys}
for key in keys:
    if after[key] and not before[key]:
        print(f"export {key}={json.dumps(after[key])}")
PY
}

eval "$(bootstrap_env_exports)"

CHALLENGE_LLM_MODEL="${GATEFORGE_AGENT_L4_UPLIFT_CHALLENGE_LLM_MODEL:-${LLM_MODEL:-${GATEFORGE_GEMINI_MODEL:-${GEMINI_MODEL:-}}}}"

release_run_lock() {
  python3 - "$LOCK_PATH" "$$" <<'PY'
import json
import sys
from pathlib import Path

lock_path = Path(sys.argv[1])
current_pid = int(sys.argv[2] or 0)
if not lock_path.exists():
    raise SystemExit(0)
payload = {}
try:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
except Exception:
    lock_path.unlink(missing_ok=True)
    raise SystemExit(0)
if int(payload.get("pid") or 0) == current_pid:
    lock_path.unlink(missing_ok=True)
PY
}

acquire_run_lock() {
  python3 - "$LOCK_PATH" "$$" "$RUN_ID" "$RUN_ROOT" "$BASE_TASKSET" "$PACK_ID" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

lock_path = Path(sys.argv[1])
current_pid = int(sys.argv[2] or 0)
run_id = str(sys.argv[3] or "")
run_root = str(sys.argv[4] or "")
base_taskset = str(sys.argv[5] or "")
pack_id = str(sys.argv[6] or "")

def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

if lock_path.exists():
    payload = {}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    active_pid = int(payload.get("pid") or 0)
    if active_pid and _pid_alive(active_pid) and active_pid != current_pid:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "active_run_lock",
                    "active_pid": active_pid,
                    "active_run_id": str(payload.get("run_id") or ""),
                    "active_run_root": str(payload.get("run_root") or ""),
                    "lock_path": str(lock_path),
                }
            )
        )
        raise SystemExit(3)
    lock_path.unlink(missing_ok=True)

payload = {
    "schema_version": "agent_modelica_realism_run_lock_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "pid": current_pid,
    "run_id": run_id,
    "run_root": run_root,
    "base_taskset": base_taskset,
    "pack_id": pack_id,
}
lock_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload))
PY
}

trap release_run_lock EXIT
acquire_run_lock

python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 init-run \
  --out-dir "$OUT_DIR" \
  --run-root "$RUN_ROOT" \
  --run-id "$RUN_ID" \
  --pack-id "$PACK_ID" \
  --pack-version "$PACK_VERSION" \
  --pack-track "$PACK_TRACK" \
  --acceptance-scope "$ACCEPTANCE_SCOPE" \
  --base-taskset "$BASE_TASKSET" \
  --lock-path "$LOCK_PATH" \
  --update-latest "$UPDATE_LATEST" >/dev/null

stage_update() {
  local stage="$1"
  local status="$2"
  local exit_code="${3:-0}"
  local summary_path="${4:-}"
  local details_json="${5:-{}}"
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 stage-update \
    --run-root "$RUN_ROOT" \
    --stage "$stage" \
    --status "$status" \
    --exit-code "$exit_code" \
    --summary-path "$summary_path" \
    --details-json "$details_json" >/dev/null
}

write_preflight_blocked() {
  python3 - "$RUN_ROOT" "$PACK_ID" "$PACK_VERSION" "$PACK_TRACK" "$ACCEPTANCE_SCOPE" "$1" "$2" "$3" "$4" "$5" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

run_root = Path(sys.argv[1])
pack_id = str(sys.argv[2] or "")
pack_version = str(sys.argv[3] or "")
pack_track = str(sys.argv[4] or "")
acceptance_scope = str(sys.argv[5] or "")
backend = str(sys.argv[6] or "")
challenge_planner_backend = str(sys.argv[7] or "")
challenge_llm_model = str(sys.argv[8] or "")
docker_access = str(sys.argv[9] or "")
blockers = json.loads(sys.argv[10] or "[]")

preflight = {
    "schema_version": "agent_modelica_realism_environment_preflight_v1",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "BLOCKED",
    "pack_id": pack_id,
    "pack_version": pack_version,
    "pack_track": pack_track,
    "acceptance_scope": acceptance_scope,
    "backend": backend,
    "challenge_planner_backend": challenge_planner_backend,
    "challenge_llm_model": challenge_llm_model or None,
    "docker_access": docker_access,
    "blockers": blockers,
}
md_lines = [
    "# Agent Modelica Realism Evidence Preflight",
    "",
    "- status: `BLOCKED`",
    f"- backend: `{backend}`",
    f"- challenge_planner_backend: `{challenge_planner_backend}`",
    f"- challenge_llm_model: `{challenge_llm_model or ''}`",
    f"- docker_access: `{docker_access}`",
    f"- blockers: `{blockers}`",
]
(run_root / "environment_preflight_summary.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")
(run_root / "environment_preflight_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print(json.dumps(preflight))
PY
}

requires_default_live_stack=0
if [ -z "$CHALLENGE_EXECUTOR_CMD" ] && [ -z "$MAIN_SWEEP_EXECUTOR_CMD" ] && [ -z "$NIGHT_SWEEP_EXECUTOR_CMD" ] && [ -z "$MAIN_L5_L3_EXECUTOR_CMD" ] && [ -z "$MAIN_L5_L4_EXECUTOR_CMD" ] && [ -z "$NIGHT_L5_L3_EXECUTOR_CMD" ] && [ -z "$NIGHT_L5_L4_EXECUTOR_CMD" ]; then
  requires_default_live_stack=1
fi

requires_gemini_env=0
for planner_backend in "$CHALLENGE_PLANNER_BACKEND" "$MAIN_PLANNER_BACKEND" "$NIGHT_PLANNER_BACKEND"; do
  if [ "$planner_backend" = "gemini" ]; then
    requires_gemini_env=1
    break
  fi
done

stage_update "preflight" "RUNNING" 0 "$RUN_ROOT/environment_preflight_summary.json"
docker_access="skipped"
blockers_json="[]"
if [ "$requires_default_live_stack" = "1" ]; then
  if [ "$requires_gemini_env" = "1" ]; then
    blockers_json="$(python3 - "$CHALLENGE_LLM_MODEL" <<'PY'
import json
import os
import sys

challenge_llm_model = str(sys.argv[1] or "").strip()
blockers = []
if not challenge_llm_model:
    blockers.append("missing_llm_model")
if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
    blockers.append("missing_gemini_api_key")
print(json.dumps(blockers))
PY
)"
  fi

  if [ "$BACKEND" = "openmodelica_docker" ]; then
    if docker ps >/dev/null 2>&1; then
      docker_access="ok"
    else
      docker_access="unavailable"
      blockers_json="$(python3 - "$blockers_json" <<'PY'
import json
import sys
blockers = json.loads(sys.argv[1] or "[]")
if "docker_unavailable" not in blockers:
    blockers.append("docker_unavailable")
print(json.dumps(blockers))
PY
)"
    fi
  fi
fi

stale_taskset_blockers="$(python3 - "$BASE_TASKSET" "$CURRENT_BUILDER_SOURCE_PATH" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

taskset_path = Path(sys.argv[1])
builder_path = Path(sys.argv[2])
blockers = []
manifest_path = taskset_path.parent / "manifest.json"
if manifest_path.exists() and builder_path.exists():
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}
    provenance = manifest.get("builder_provenance") if isinstance(manifest.get("builder_provenance"), dict) else {}
    taskset_builder_sha = str(provenance.get("builder_source_sha") or "").strip()
    current_builder_sha = hashlib.sha256(builder_path.read_bytes()).hexdigest()
    if taskset_builder_sha and taskset_builder_sha != current_builder_sha:
        blockers.append("stale_base_taskset")
print(json.dumps(blockers))
PY
)"
if [ "$stale_taskset_blockers" != "[]" ]; then
  blockers_json="$(python3 - "$blockers_json" "$stale_taskset_blockers" <<'PY'
import json
import sys

blockers = json.loads(sys.argv[1] or "[]")
extras = json.loads(sys.argv[2] or "[]")
for item in extras:
    if item not in blockers:
        blockers.append(item)
print(json.dumps(blockers))
PY
)"
fi

if [ "$blockers_json" != "[]" ]; then
  write_preflight_blocked "$BACKEND" "$CHALLENGE_PLANNER_BACKEND" "$CHALLENGE_LLM_MODEL" "$docker_access" "$blockers_json" >/dev/null
  stage_update "preflight" "BLOCKED" 2 "$RUN_ROOT/environment_preflight_summary.json" "{\"blockers\": $blockers_json}"
  python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 finalize-run \
    --out-dir "$OUT_DIR" \
    --run-root "$RUN_ROOT" \
    --update-latest 0 >/dev/null
  cat "$RUN_ROOT/final_run_summary.json"
  exit 2
fi
stage_update "preflight" "PASS" 0 "$RUN_ROOT/environment_preflight_summary.json"

set +e
GATEFORGE_AGENT_L4_UPLIFT_OUT_DIR="$RUN_ROOT" \
GATEFORGE_AGENT_L4_UPLIFT_BASE_TASKSET="$BASE_TASKSET" \
GATEFORGE_AGENT_L4_UPLIFT_SCALES="$SCALES" \
GATEFORGE_AGENT_L4_UPLIFT_PROFILES="$PROFILES" \
GATEFORGE_AGENT_L4_UPLIFT_FAILURE_TYPES="$FAILURE_TYPES" \
GATEFORGE_AGENT_L4_UPLIFT_REQUIRED_CATEGORIES="$REQUIRED_CATEGORIES" \
GATEFORGE_AGENT_L4_UPLIFT_PER_FAILURE_TYPE_CAP="$PER_FAILURE_TYPE_CAP" \
GATEFORGE_AGENT_L4_UPLIFT_HOLDOUT_RATIO="$HOLDOUT_RATIO" \
GATEFORGE_AGENT_L4_UPLIFT_SPLIT_SEED="$SPLIT_SEED" \
GATEFORGE_AGENT_L4_UPLIFT_PACK_ID="$PACK_ID" \
GATEFORGE_AGENT_L4_UPLIFT_PACK_VERSION="$PACK_VERSION" \
GATEFORGE_AGENT_L4_UPLIFT_PACK_TRACK="$PACK_TRACK" \
GATEFORGE_AGENT_L4_UPLIFT_ACCEPTANCE_SCOPE="$ACCEPTANCE_SCOPE" \
GATEFORGE_AGENT_L4_UPLIFT_CONTINUE_ON_WEAK_BASELINE="$CONTINUE_ON_WEAK_BASELINE" \
GATEFORGE_AGENT_L4_UPLIFT_REALISM_MODE="$REALISM_MODE" \
GATEFORGE_AGENT_L4_UPLIFT_ENABLE_NIGHT="$NIGHT_ENABLED" \
GATEFORGE_AGENT_L4_UPLIFT_RUN_ROOT="$RUN_ROOT" \
GATEFORGE_AGENT_LIVE_REQUEST_LEDGER_PATH="$LIVE_LEDGER_PATH" \
GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN="$LIVE_MAX_REQUESTS_PER_RUN" \
GATEFORGE_AGENT_LIVE_MAX_CONSECUTIVE_429="$LIVE_MAX_CONSECUTIVE_429" \
GATEFORGE_AGENT_LIVE_BACKOFF_BASE_SEC="$LIVE_BACKOFF_BASE_SEC" \
GATEFORGE_AGENT_LIVE_BACKOFF_MAX_SEC="$LIVE_BACKOFF_MAX_SEC" \
bash scripts/run_agent_modelica_l4_uplift_evidence_v0.sh
UPLIFT_RC=$?
set -e

stage_update "realism_summary" "RUNNING" 0 "$RUN_ROOT/realism_internal_summary.json"
REALISM_SUMMARY_RC=0
if [ -f "$RUN_ROOT/summary.json" ]; then
  set +e
  python3 -m gateforge.agent_modelica_realism_summary_v1 \
    --evidence-summary "$RUN_ROOT/summary.json" \
    --challenge-summary "$RUN_ROOT/challenge/frozen_summary.json" \
    --challenge-manifest "$RUN_ROOT/challenge/manifest.json" \
    --taskset "$RUN_ROOT/challenge/taskset_frozen.json" \
    --l3-run-results "$RUN_ROOT/main_l5/l3/run2/run_results.json" \
    --l3-quality-summary "$RUN_ROOT/main_l5/l3/run2/diagnostic_quality_summary.json" \
    --l4-ab-compare-summary "$RUN_ROOT/main_l5/l4/ab_compare_summary.json" \
    --l5-summary "$RUN_ROOT/main_l5/l5_eval_summary.json" \
    --out "$RUN_ROOT/realism_internal_summary.json" \
    --report-out "$RUN_ROOT/realism_internal_summary.md" >/dev/null
  REALISM_SUMMARY_RC=$?
  set -e
else
  REALISM_SUMMARY_RC=1
fi
if [ "$REALISM_SUMMARY_RC" -eq 0 ] && [ -f "$RUN_ROOT/realism_internal_summary.json" ]; then
  stage_update "realism_summary" "PASS" "$REALISM_SUMMARY_RC" "$RUN_ROOT/realism_internal_summary.json"
else
  stage_update "realism_summary" "FAIL" "$REALISM_SUMMARY_RC" "$RUN_ROOT/realism_internal_summary.json"
fi

python3 -m gateforge.agent_modelica_realism_run_lifecycle_v1 finalize-run \
  --out-dir "$OUT_DIR" \
  --run-root "$RUN_ROOT" \
  --update-latest "$UPDATE_LATEST" >/dev/null

cat "$RUN_ROOT/final_run_summary.json"
if [ "$UPLIFT_RC" -ne 0 ]; then
  exit "$UPLIFT_RC"
fi
