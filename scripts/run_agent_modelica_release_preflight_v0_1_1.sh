#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_AGENT_RELEASE_OUT_DIR:-artifacts/release_v0_1_1}"
RUN_LIVE_SMOKE="${GATEFORGE_AGENT_RELEASE_RUN_LIVE_SMOKE:-0}"
REQUIRE_REAL_OMC_BACKEND="${GATEFORGE_AGENT_RELEASE_REQUIRE_REAL_OMC_BACKEND:-1}"

PROFILE_PATH="${GATEFORGE_AGENT_MVP_PROFILE_PATH:-benchmarks/private/agent_modelica_mvp_repair_v1.json}"
if [ ! -f "$PROFILE_PATH" ]; then
  PROFILE_PATH="benchmarks/agent_modelica_mvp_repair_v1.json"
fi

mkdir -p "$OUT_DIR"

python3 -m gateforge.agent_modelica_learning_preflight_v1 \
  --profile "$PROFILE_PATH" \
  --out "$OUT_DIR/learning_preflight.json" \
  --report-out "$OUT_DIR/learning_preflight.md"

python3 -m gateforge.agent_modelica_private_asset_guard_v1 \
  --repo-root "$ROOT_DIR" \
  --out "$OUT_DIR/private_asset_guard.json" \
  --report-out "$OUT_DIR/private_asset_guard.md"

if [ "$RUN_LIVE_SMOKE" = "1" ]; then
  SOURCE_MODEL_PATH="${GATEFORGE_AGENT_RELEASE_SMOKE_SOURCE_MODEL_PATH:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/exported/demo_repo_shard_base_a/Base/A/A1.mo}"
  MUTATED_MODEL_PATH="${GATEFORGE_AGENT_RELEASE_SMOKE_MUTATED_MODEL_PATH:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutants/semantic_regression/mdl_a1_393f6bb7/mat_mdl_a1_393f6bb7_semantic_regression_301500.mo}"
  python3 -m gateforge.agent_modelica_live_executor_gemini_v1 \
    --task-id "${GATEFORGE_AGENT_RELEASE_SMOKE_TASK_ID:-release-smoke-1}" \
    --failure-type "${GATEFORGE_AGENT_RELEASE_SMOKE_FAILURE_TYPE:-semantic_regression}" \
    --expected-stage "${GATEFORGE_AGENT_RELEASE_SMOKE_EXPECTED_STAGE:-simulate}" \
    --source-model-path "$SOURCE_MODEL_PATH" \
    --mutated-model-path "$MUTATED_MODEL_PATH" \
    --max-rounds "${GATEFORGE_AGENT_RELEASE_SMOKE_MAX_ROUNDS:-2}" \
    --timeout-sec "${GATEFORGE_AGENT_RELEASE_SMOKE_TIMEOUT_SEC:-90}" \
    --planner-backend "${GATEFORGE_AGENT_RELEASE_SMOKE_PLANNER_BACKEND:-rule}" \
    --backend "${GATEFORGE_AGENT_RELEASE_SMOKE_BACKEND:-openmodelica_docker}" \
    --out "$OUT_DIR/live_smoke_executor.json"
else
  python3 - "$OUT_DIR/live_smoke_executor.json" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"status": "NEEDS_REVIEW", "executor_status": "SKIPPED", "reason": "live_smoke_disabled"}, indent=2), encoding="utf-8")
print(json.dumps({"status": "NEEDS_REVIEW", "executor_status": "SKIPPED"}))
PY
fi

python3 - "$OUT_DIR" "$RUN_LIVE_SMOKE" "$REQUIRE_REAL_OMC_BACKEND" <<'PY'
import json
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
run_live_smoke = str(sys.argv[2]).strip() == "1"
require_real_omc = str(sys.argv[3]).strip() == "1"
learning = json.loads((out_dir / "learning_preflight.json").read_text(encoding="utf-8"))
private_guard = json.loads((out_dir / "private_asset_guard.json").read_text(encoding="utf-8"))
live_smoke = json.loads((out_dir / "live_smoke_executor.json").read_text(encoding="utf-8"))

status = "PASS"
reasons = []
if str(learning.get("status") or "") != "PASS":
    status = "FAIL"
    reasons.append("learning_preflight_not_pass")
if str(private_guard.get("status") or "") != "PASS":
    status = "FAIL"
    reasons.append("private_asset_guard_not_pass")
live_status = str(live_smoke.get("executor_status") or live_smoke.get("status") or "")
if status != "FAIL" and live_status in {"", "SKIPPED", "NEEDS_REVIEW"}:
    status = "NEEDS_REVIEW"
if live_status and live_status not in {"PASS", "NEEDS_REVIEW", "SKIPPED"}:
    status = "FAIL"
    reasons.append("live_smoke_not_pass")

live_backend = str(live_smoke.get("backend_used") or "").strip().lower()
if run_live_smoke and require_real_omc and live_backend not in {"omc", "openmodelica_docker"}:
    status = "FAIL"
    reasons.append("live_smoke_backend_not_real_omc")

live_fallback = bool(live_smoke.get("backend_fallback_to_syntax"))
if run_live_smoke and require_real_omc and live_fallback:
    status = "FAIL"
    reasons.append("live_smoke_backend_fallback_to_syntax")

payload = {
    "status": status,
    "profile_path": str(((learning.get("inputs") or {}).get("profile")) or ""),
    "learning_preflight_status": str(learning.get("status") or ""),
    "private_asset_guard_status": str(private_guard.get("status") or ""),
    "live_smoke_status": live_status or "SKIPPED",
    "live_smoke_backend_used": live_backend,
    "require_real_omc_backend": require_real_omc,
    "reasons": reasons,
    "paths": {
        "learning_preflight": str(out_dir / "learning_preflight.json"),
        "private_asset_guard": str(out_dir / "private_asset_guard.json"),
        "live_smoke_executor": str(out_dir / "live_smoke_executor.json"),
    },
}
(out_dir / "release_preflight_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload))
if status == "FAIL":
    raise SystemExit(1)
PY
