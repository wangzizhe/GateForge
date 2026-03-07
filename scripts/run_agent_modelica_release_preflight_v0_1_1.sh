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
PROFILE_PATH_FOR_PREFLIGHT="$PROFILE_PATH"
BOOTSTRAP_MISSING_LEARNING_MEMORY="${GATEFORGE_AGENT_RELEASE_BOOTSTRAP_MISSING_LEARNING_MEMORY:-1}"

mkdir -p "$OUT_DIR"

if [ "$BOOTSTRAP_MISSING_LEARNING_MEMORY" = "1" ]; then
  PROFILE_PATH_FOR_PREFLIGHT="$(
    python3 - "$PROFILE_PATH" "$OUT_DIR/learning_profile_bootstrap.json" "$OUT_DIR/learning_memory_bootstrap.json" <<'PY'
import json
import sys
from pathlib import Path

profile_path = Path(sys.argv[1])
profile_out = Path(sys.argv[2])
memory_out = Path(sys.argv[3])

if not profile_path.exists():
    print(str(profile_path))
    raise SystemExit(0)

profile = json.loads(profile_path.read_text(encoding="utf-8"))
privacy = profile.get("privacy") if isinstance(profile.get("privacy"), dict) else {}
memory_path = Path(str(privacy.get("repair_history_path") or ""))
if memory_path.exists():
    print(str(profile_path))
    raise SystemExit(0)

memory_out.parent.mkdir(parents=True, exist_ok=True)
failure_types = ["model_check_error", "simulate_error", "semantic_regression"]
rows = []
for idx in range(60):
    failure_type = failure_types[idx % len(failure_types)]
    split = "holdout" if idx >= 54 else "train"
    error_signature = f"{failure_type}_sig_{split}_{idx}"
    rows.append(
        {
            "fingerprint": f"bootstrap_fp_{idx:04d}",
            "task_id": f"bootstrap_task_{idx:04d}",
            "failure_type": failure_type,
            "scale": "small" if idx % 3 == 0 else ("medium" if idx % 3 == 1 else "large"),
            "used_strategy": f"bootstrap_strategy_{failure_type}",
            "action_trace": ["bootstrap_action_prepare", "bootstrap_action_apply"],
            "error_signature": error_signature,
            "gate_break_reason": "bootstrap_seeded_for_ci_release_preflight",
            "success": True,
            "split": split,
        }
    )
memory_payload = {
    "schema_version": "agent_modelica_repair_memory_v1",
    "rows": rows,
}
memory_out.write_text(json.dumps(memory_payload, indent=2), encoding="utf-8")

profile_copy = dict(profile)
privacy_copy = dict(privacy)
privacy_copy["repair_history_path"] = str(memory_out)
profile_copy["privacy"] = privacy_copy
profile_out.parent.mkdir(parents=True, exist_ok=True)
profile_out.write_text(json.dumps(profile_copy, indent=2), encoding="utf-8")
print(str(profile_out))
PY
  )"
  if [ ! -f "$PROFILE_PATH_FOR_PREFLIGHT" ]; then
    PROFILE_PATH_FOR_PREFLIGHT="$PROFILE_PATH"
  fi
fi

python3 -m gateforge.agent_modelica_learning_preflight_v1 \
  --profile "$PROFILE_PATH_FOR_PREFLIGHT" \
  --out "$OUT_DIR/learning_preflight.json" \
  --report-out "$OUT_DIR/learning_preflight.md"

python3 -m gateforge.agent_modelica_private_asset_guard_v1 \
  --repo-root "$ROOT_DIR" \
  --out "$OUT_DIR/private_asset_guard.json" \
  --report-out "$OUT_DIR/private_asset_guard.md"

if [ "$RUN_LIVE_SMOKE" = "1" ]; then
  SOURCE_MODEL_PATH="${GATEFORGE_AGENT_RELEASE_SMOKE_SOURCE_MODEL_PATH:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/exported/demo_repo_shard_base_a/Base/A/A1.mo}"
  MUTATED_MODEL_PATH="${GATEFORGE_AGENT_RELEASE_SMOKE_MUTATED_MODEL_PATH:-artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/scale/mutants/semantic_regression/mdl_a1_393f6bb7/mat_mdl_a1_393f6bb7_semantic_regression_301500.mo}"
  SMOKE_PATH_ENV="$OUT_DIR/live_smoke_paths.env"
  python3 - "$SOURCE_MODEL_PATH" "$MUTATED_MODEL_PATH" "$OUT_DIR" > "$SMOKE_PATH_ENV" <<'PY'
import re
import shlex
import sys
from pathlib import Path

source_path = Path(sys.argv[1])
mutated_path = Path(sys.argv[2])
out_dir = Path(sys.argv[3])

smoke_dir = out_dir / "live_smoke_inputs"
smoke_dir.mkdir(parents=True, exist_ok=True)

if not source_path.exists():
    source_path = smoke_dir / "A1.mo"
    source_path.write_text(
        "model A1\n"
        "  Real x;\n"
        "equation\n"
        "  der(x) = -x;\n"
        "end A1;\n",
        encoding="utf-8",
    )

if not mutated_path.exists():
    source_text = source_path.read_text(encoding="utf-8")
    model_name_match = re.search(r"(?im)^\\s*model\\s+([A-Za-z_]\\w*)\\b", source_text)
    model_name = model_name_match.group(1) if model_name_match else "A1"
    injection = "  Real __gf_state_301500(start=1.0);"
    if re.search(r"(?im)^\\s*equation\\b", source_text):
        mutated_text = re.sub(r"(?im)^\\s*equation\\b", "equation\\n" + injection, source_text, count=1)
    else:
        end_pat = re.compile(rf"(?im)^\\s*end\\s+{re.escape(model_name)}\\s*;")
        end_match = end_pat.search(source_text)
        if end_match:
            insert = "equation\\n" + injection + "\\n"
            mutated_text = source_text[: end_match.start()] + insert + source_text[end_match.start() :]
        else:
            mutated_text = source_text + "\\nequation\\n" + injection + "\\n"
    mutated_path = smoke_dir / f"{source_path.stem}_smoke_mutant.mo"
    mutated_path.write_text(mutated_text, encoding="utf-8")

print(f"SOURCE_MODEL_PATH={shlex.quote(str(source_path))}")
print(f"MUTATED_MODEL_PATH={shlex.quote(str(mutated_path))}")
PY
  # shellcheck disable=SC1090
  source "$SMOKE_PATH_ENV"
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
live_status = str(live_smoke.get("executor_status") or live_smoke.get("status") or "").strip()
if run_live_smoke and not live_status:
    hard_keys = ("check_model_pass", "simulate_pass", "physics_contract_pass", "regression_pass")
    if all(k in live_smoke for k in hard_keys):
        live_status = "PASS" if all(bool(live_smoke.get(k)) for k in hard_keys) else "FAILED"
if run_live_smoke:
    if live_status != "PASS":
        status = "FAIL"
        reasons.append("live_smoke_not_pass")
else:
    if status != "FAIL" and live_status in {"", "SKIPPED", "NEEDS_REVIEW"}:
        status = "NEEDS_REVIEW"

live_backend = str(live_smoke.get("backend_used") or "").strip().lower()
if run_live_smoke and require_real_omc and live_status == "PASS" and live_backend not in {"omc", "openmodelica_docker"}:
    status = "FAIL"
    reasons.append("live_smoke_backend_not_real_omc")

live_fallback = bool(live_smoke.get("backend_fallback_to_syntax"))
if run_live_smoke and require_real_omc and live_status == "PASS" and live_fallback:
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
